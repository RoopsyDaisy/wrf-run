# Workflow Improvements

Running list of proposed improvements to wrf-run, captured during the May 2026
handover and fresh-setup pass. Roughly ordered by effort × impact. Each entry
notes context — the surrounding situation that prompted the idea — so future
operators can judge whether the rationale still applies before acting.

---

## High value, small effort

### 1. Fix `setup_wps_wrf.py` child-process Python resolution

**Context:** During the first real run, `setup_wps_wrf.py` failed at
`import numpy` even though the conda env clearly had numpy. Cause:
`setup_wps_wrf.py` invokes its child scripts (HRRR downloader, run_geogrid,
run_ungrib, ...) with bare `python`, which resolves through `PATH`. Unless
the launching shell has activated the conda env, child processes find the
system Python instead.

Current workaround: launch with `bash -l -c '...'` so the bashrc activates
the env before the process tree starts.

**Better fix:** have `fires/run_budget_day.py` either (a) source the repo's
bashrc before exec'ing `setup_wps_wrf.py`, or (b) prepend the conda env's
`bin/` to `PATH` in its own environment, or (c) upstream a patch to
`setup_wps_wrf.py` to use `sys.executable` for child processes (cleanest, but
JaredLee's repo).

### 2. Add `wps_variant` to `configs/settings.yaml`

**Context:** Switching from Derecho (`WPS-4.6-dmpar`) to Casper
(`WPS-4.6-dmpar-casper`) currently requires sed-editing
`configs/templates/workflow/*.yaml` and `namelist.wps.hrrr`.

**Fix:** add `wps_variant: dmpar` to settings, change templates to use
`WPS-4.6-{{ wps_variant }}`. One-line change to swap platforms.

### 3. Keep `environment.exact.yml` in sync with pip installs

**Context:** `environment.exact.yml` is a frozen conda export but doesn't
capture `pip install wget` (or any future pip-only packages). A user who
rebuilds from `.exact.yml` ends up with a broken env.

**Fix:** after any `pip install` into the env, regenerate
`.exact.yml` with `conda env export --prefix /glade/work/$USER/conda-envs/workflow`
(which includes pip packages in the output). Or commit a separate
`pip-requirements.txt`.

### 4. Investigate `~ljaeger/trim.sh`

**Context:** Lorn's home dir has `trim.sh` plus `trim_manifest_full.csv` (4.5 MB)
and `trim_full.log` at `/glade/u/home/ljaeger/`. Looks like a post-hoc wrfout
trimmer — likely the thing that actually shrinks output files (see #5). We
never confirmed where it sits in his workflow (manual / cron / post-cleanup),
and Lorn is no longer reachable.

**Fix:** read the script and manifest, port whatever it does into
`fires/` or `scripts/` before any multi-day production sweep. Until then,
expect full ~190 MB / 220-var wrfout files and budget scratch accordingly.

### 5. Verify `iofields_fire.txt` actually trims output

**Context:** `iofields_fire.txt` is meant to limit which fields land in
wrfout, but empirically every wrfout in both Lorn's and our scratch trees has
the full 220 variables and `rsl.out.0000` shows "Problem reading
iofields_fire.txt at line N" warnings for every line. Three possibilities:
(a) format is silently broken and trimming happens downstream via `trim.sh`
(see #4), (b) the `+VarName` syntax in `fires/generate_configs.py`'s
`IOFIELDS_CONTENT` is wrong, (c) a different namelist switch is needed.

**Fix:** check the WRF Registry / iofields docs for current syntax, fix
`IOFIELDS_CONTENT` if wrong, and confirm by counting variables in a single
test wrfout. If the file is decorative, document that and rely on the trim
pipeline.

### 6. Doc cross-ref linting

**Context:** `docs/ARCHITECTURE.md` (formerly `misc/WORKFLOW_OVERVIEW.md`)
referenced 7 files that don't exist in the repo. Stale references silently rot.

**Fix:** add a pre-commit or CI check that greps `docs/*.md` for
repo-relative paths (`fires/x.py`, `scripts/y.sh`, `configs/z.yaml`) and
fails if any don't exist.

---

## Higher value, larger effort

### 7. Parallel HRRR downloads

**Context:** `wps_wrf_workflow/download_hrrr_from_aws_or_gc.py` downloads one
URL at a time. ~62 files per fire/day at ~10s each = 10+ minutes per fresh
fire/day, all sequential. Multi-day sweeps are bottlenecked by this.

**Fix:** wrap downloads in `concurrent.futures.ThreadPoolExecutor` (8-16
workers). The interp script (`scripts/fix_missing_hrrr_links.py`) already
uses this pattern; pull the same trick upstream.

### 8. Auto-trigger HRRR fill-in on missing files

**Context:** When AWS/GC is missing a HRRR file (10-20% of days per Lorn),
the download script silently leaves a hole, the workflow proceeds, and WRF
later crashes or produces bad output. `scripts/fix_missing_hrrr_links.py`
exists to interpolate missing hours, but is run manually after the fact.

**Fix:** have the download script return a list of files it couldn't fetch,
and have `run_budget_day.py` automatically run the interp step before
proceeding to WPS.

### 9. Auto cleanup when scratch fills

**Context:** Lorn manually runs `fires/cleanup_day.py` when scratch fills up
and jobs stop. Easy to forget, easy to lose progress.

**Fix:** cron-style check (or part of `run.sh`) that runs
`gladequota`, identifies completed day-runs, and `cleanup_day.py --execute`s
them when usage exceeds a threshold (e.g., 80%). Carefully: must not delete
in-progress runs.

### 10. Audit and prune `misc/`

**Context:** `misc/` contains ~20 historical helper scripts (older command
runners, ad-hoc reporting, HRRR rerun fixers). Some may still be useful;
others are dead. Currently dead weight that confuses cross-referencing.

**Fix:** classify each into (a) promote to `scripts/` or `fires/`,
(b) delete, (c) move to a clearly-labeled `legacy/` subdir for reference.
Update `docs/ARCHITECTURE.md` accordingly.

---

## Lower priority / deferred

### 11. Cleaner placeholders in `namelist.wps.hrrr`

**Context:** Lines 33, 37, and 40 contain values like
`UM_WRF_1Dom1km` and `20250324_00` that *look* like real config but are
actually placeholders rewritten by `setup_wps_wrf.py` at runtime. They can be
mistaken for production config and "corrected" wrongly.

**Fix:** replace with obvious placeholder syntax (e.g., `<fire_id>`,
`<cycle>`) — but only after confirming `setup_wps_wrf.py` does string-replace
on whatever literals it expects. Otherwise we break the workflow.

### 12. Parameterize `scripts/alert_usage.sh`

**Context:** Has `lornjaeger@proton.me` hardcoded. Currently safe at rest
(manual `while true` loop), but a footgun for the next operator who
forgets to edit before running.

**Fix:** read email from `$ALERT_EMAIL` env var; if unset, log instead of
mailing.

### 13. Reduce coupling to JaredLee's `wps_wrf_workflow/`

**Context:** `wps_wrf_workflow/` is vendored upstream code. Several
improvements above (bashrc-aware invocation, parallel downloads,
sys.executable for children) require either patching that code in-place
(diverging from upstream) or maintaining a fork.

**Fix (long-term):** evaluate whether maintaining a fork is cheaper than the
current "vendored without changes" pattern. If yes, formally fork on GitHub
and add a CHANGES log of our deltas.

### 14. Multi-fire test in setup verification

**Context:** `docs/SETUP.md` walks through 1 fire. The "share ungrib output
between fires on the same day" code path in `run_budget_day.py` is therefore
untested by the setup smoke flow.

**Fix:** add a 2-fire same-day test as the final step in SETUP.md so the
shared-ungrib path is exercised before someone goes to production.

### 15. Audit `notebooks/tldr.ipynb`

**Context:** Inherited from Lorn with hardcoded `ljaeger` paths in code cells.
Never run on Rupert's account, purpose unverified.

**Fix:** open it, decide whether the analysis is still useful. If yes,
parameterize the paths via `configs/settings.yaml`. If no, delete.

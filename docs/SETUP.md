# SETUP — wrf-run on a fresh NCAR HPC account

This guide takes a new operator from zero to a successful end-to-end run on
NCAR Derecho. It is the canonical fresh-setup procedure; if it doesn't work,
the gap is a bug to fix in this doc, not something to memorize.

For an explanation of *what* the workflow does, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Prerequisites

- An NCAR HPC account (you can SSH to `derecho.hpc.ucar.edu`).
- An NCAR project allocation. Check yours at <https://sam.ucar.edu>; this guide
  assumes `P48500047` (the project the WRF wildfire effort is allocated to).
  If you need to be added, email NCAR support with the project number.
- A colleague's account that has the pre-compiled WRF/WPS binaries (`bin/`
  tree). The repo does not ship binaries; you copy them from someone who
  already has a working compile.

## 1. Clone the repo

```bash
cd ~
git clone https://github.com/lorn-jaeger/wrf-run.git
cd wrf-run
```

## 2. Copy the WRF/WPS binaries

The `bin/` tree is ~2.9 G of compiled WRF 4.6 and WPS 4.6 (both `dmpar` for
Derecho and `dmpar-casper` for Casper). It is not committed.

```bash
# Replace <source-user> with whoever has a working compile
cp -a /glade/u/home/<source-user>/wrf-run/bin /glade/u/home/$USER/wrf-run/bin
```

Verify:

```bash
ls bin/                                       # WRF-4.6, WPS-4.6-dmpar, WPS-4.6-dmpar-casper
stat -c '%s %n' bin/WRF-4.6/main/wrf.exe      # ~60 MB; if much smaller it's a broken symlink
```

## 3. Create your settings file

```bash
cp configs/settings.yaml.example configs/settings.yaml
$EDITOR configs/settings.yaml                 # set `user` and `project`
```

`configs/settings.yaml` is gitignored. The two required keys (`user` and
`project`) drive all the per-user paths in the templates via
`fires/settings.py`. Optional explicit overrides for `home_root`,
`scratch_root`, `workflow_root`, and `grib_root` are commented out in the
example file — leave them commented unless you have a reason.

## 4. Set up the shell environment

NCAR SSH sessions read `~/.bash_profile` (login shell). Interactive subshells
read `~/.bashrc`. We want both to source the repo's committed `bashrc` so
module loads, conda activation, and aliases work everywhere.

```bash
echo '[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc"' > ~/.bash_profile
echo '[ -f "$HOME/wrf-run/bashrc" ] && source "$HOME/wrf-run/bashrc"' > ~/.bashrc
```

If you already have a `~/.bashrc` or `~/.bash_profile` with personal config,
just add the relevant `source` line; don't overwrite.

## 5. Create the conda env

```bash
module load conda
conda env create -f environment.yml --prefix /glade/work/$USER/conda-envs/workflow
```

Takes 3-5 minutes. Lives in `/glade/work` rather than `/glade/u/home` to keep
the env out of nightly home-directory backups.

Verify:

```bash
bash -l -c 'python -c "import yaml, salem, wrf, f90nml, numpy, wget; print(\"imports OK\")"'
```

The repo's `bashrc` references the env by full path
(`conda activate /glade/work/$USER/conda-envs/workflow`), so opening a fresh
SSH session at this point should drop you straight into the env.

## 6. Generate per-fire configs

For a smoke test, pick one row from `fires/data/output_budget.csv`:

```bash
cat > runs_test_1fire.csv <<'EOF'
date,latitude,longitude,fire_id
2018-01-01,36.82974299485794,-120.2683502029467,fire_21458798
EOF

python fires/generate_configs.py \
    --runs-csv runs_test_1fire.csv \
    --output-dir configs/built \
    --overwrite
```

This reads `configs/templates/workflow/base.yaml` and the WRF templates,
substitutes `{{ user }}`, `{{ project }}`, `{{ home_root }}`, `{{ scratch_root }}`
from `configs/settings.yaml`, applies per-fire fire-id and lat/lon, and writes
`configs/built/workflow/<fire_id>.yaml` plus a per-fire template directory at
`configs/built/wrf/<fire_id>/`.

Spot-check the generated yaml:

```bash
cat configs/built/workflow/fire_21458798.yaml      # paths should reference YOUR username
grep '#PBS -A' configs/built/wrf/fire_21458798/submit_wrf.bash.derecho   # should show your project
```

## 7. Dry-run

```bash
python fires/run_budget_day.py --list-days --runs-file runs_test_1fire.csv
python fires/run_budget_day.py --day-index 1 --runs-file runs_test_1fire.csv \
    --dry-run --config-root configs/built/workflow
```

The dry-run prints the exact `setup_wps_wrf.py` invocation that a real run
would issue. No PBS jobs, no downloads, no compute spend.

## 8. Real run

```bash
bash -l -c 'python fires/run_budget_day.py --day-index 1 --runs-file runs_test_1fire.csv'
```

> **Why `bash -l -c`?** `setup_wps_wrf.py` invokes its child scripts (HRRR
> downloader, stage runners) with bare `python`, which resolves through `PATH`.
> A login shell sources our bashrc which puts the conda env on `PATH`; without
> it, the child processes find the system Python and fail at `import numpy`.

**Hybrid Casper / Derecho execution.** The WPS stages (geogrid, ungrib,
metgrid) submit to Casper's PBS server (queue `casper@casper-pbs`) using the
Casper-built `WPS-4.6-dmpar-casper` binary. The WRF stages (real, wrf) submit
to Derecho's `main` queue using `WRF-4.6`. This split is intentional — Lorn
discovered (and we re-discovered the hard way) that the Derecho-built
`WPS-4.6-dmpar` binary has a parallel-I/O race in metgrid that corrupts the
first met_em file. The Casper binary on Casper's filesystem doesn't.

What happens in order:

1. **HRRR download** (login node, no PBS): ~15-20 GB to
   `/glade/derecho/scratch/$USER/data/hrrr/`. Takes 5-15 min.
2. **geogrid** (Casper PBS): minutes. Output `geo_em.d0*` in the shared geogrid
   directory.
3. **ungrib** (Casper PBS): minutes.
4. **metgrid** (Casper PBS): minutes. `met_em.d0*` files.
5. **real** (Derecho PBS): minutes. Produces `wrfinput_d0*`, `wrfbdy_d01`.
6. **wrf** (Derecho PBS): the long one — 1-3+ hours wallclock. Produces
   `wrfout_d0*` files.

Monitor with:

```bash
qstat -u $USER                                              # current PBS jobs
tail -f logs/budget_runs/fire_21458798_2018-01-01.log       # workflow log
ls /glade/derecho/scratch/$USER/workflow/fire_21458798/wrf/*/wrfout_d0*  # WRF outputs as they appear
```

The run is "done" when `wrfout_d0*` count >= 12 (configurable via
`--wrfout-threshold`).

## Troubleshooting

- **`ModuleNotFoundError: No module named 'wget'`**
  The conda `wget` package is the binary; the Python module ships separately.
  `environment.yml` has both (binary via conda, Python module via pip), but
  `environment.exact.yml` only has the binary. If you used `.exact.yml`, run
  `pip install wget` into the env.

- **`ModuleNotFoundError` in a child Python process** — make sure you launched
  with `bash -l -c '...'`. See "Why `bash -l -c`?" above.

- **`PBS Account UUMM0004 unknown`** — your `configs/settings.yaml` `project`
  isn't set to `P48500047` (or whatever you're allocated to). Re-run
  `generate_configs.py` after fixing.

- **metgrid produces a corrupt first `met_em` file (`ext_pkg_open_for_write_begin`)
  and real.exe later fails opening it** — you're running the Derecho-built WPS
  binary on Derecho. Switch to `WPS-4.6-dmpar-casper` for WPS stages and route
  to the `casper@casper-pbs` queue. This is the canonical setup; see
  [configs/templates/wrf/submit_{geogrid,ungrib,metgrid}.bash.derecho](../configs/templates/wrf/).

- **`/glade/u/home/<someone-else>/...` in generated yaml** — your
  `settings.yaml` `user` isn't `$USER`. Fix and regenerate.

- **Broken symlinks under `bin/`** — the source you copied from probably has
  reorganized binaries. Run `find bin -type l -! -exec test -e {} \; -print`
  to locate them; copy from a different colleague's bin.

- **Scratch quota** — you need ~25 G of headroom for HRRR + WPS + WRF outputs
  per day. `gladequota` shows current usage.

## Disaster recovery / off-site backup

The repo is on GitHub, but the `bin/` tree (2.9 GB of compiled WRF 4.6 / WPS 4.6
binaries) is not — it lives only on NCAR. If Jeremy's original compile and our
copy both disappear, the only path back is recompiling on both Derecho and
Casper, which is a multi-day exercise. Keep a copy on the lab PC.

What to back up:

- `bin/` — the only critical asset. ~2.9 GB.
- The repo — already on GitHub, but a mirror clone is cheap insurance.
- Conda env snapshot — optional; `environment.exact.yml` is the lockfile.

What **not** to back up: `/glade/work/wrfhelp/WPS_GEOG` (1.6 TB, NCAR maintains)
or the HRRR cache (re-downloadable per run).

### Pull onto the lab PC

Run from the **lab PC**, with SSH access to Derecho configured.

```bash
LAB_BACKUP=/path/on/labpc/wrf-run-backup     # edit
mkdir -p "$LAB_BACKUP"

# bin/ tree — tar-over-SSH preserves symlinks
ssh rupertw@derecho.hpc.ucar.edu \
    'tar -C /glade/u/home/rupertw/wrf-run -czf - bin' \
    > "$LAB_BACKUP/wrf-run-bin-$(date +%Y%m%d).tar.gz"

# Repo mirror (refresh later with: git -C wrf-run.git remote update)
git -C "$LAB_BACKUP" clone --mirror git@github.com:RoopsyDaisy/wrf-run.git wrf-run.git

# Optional: conda env snapshot
ssh rupertw@derecho.hpc.ucar.edu \
    'module load conda && conda env export -p /glade/work/rupertw/conda-envs/workflow' \
    > "$LAB_BACKUP/conda-workflow-$(date +%Y%m%d).yml"
```

### Restore on a fresh NCAR account

```bash
git clone git@github.com:RoopsyDaisy/wrf-run.git ~/wrf-run
scp labpc:$LAB_BACKUP/wrf-run-bin-YYYYMMDD.tar.gz ~/
tar -xzf ~/wrf-run-bin-YYYYMMDD.tar.gz -C ~/wrf-run/
# Then continue from step 3 above (settings.yaml).
```

## What's next

- Read [docs/ARCHITECTURE.md](ARCHITECTURE.md) for how the workflow is wired
  internally.
- For a multi-day run, generate configs for the full
  `fires/data/output_budget.csv` and use [run.sh](../run.sh) for queue-throttled
  parallel execution across days.
- Cleanup of completed days: `python fires/cleanup_day.py --day-index N --execute`.

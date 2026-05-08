# Questions for Lorn

Open questions and deferred items only. Resolved items are deleted once acted on
(answer lives in code/commits/lab knowledge, not here).

---

## To raise

- **Hybrid Casper / Derecho is the working setup, right?** Per his answer to
  the WPS-variant question (1.3), "generally Derecho so just `-dmpar`". But his
  actual production runs in scratch tell a different story:
  WPS stages (geogrid, ungrib, metgrid) run on Casper with the
  `WPS-4.6-dmpar-casper` binary, WRF stages (real, wrf) run on Derecho main.
  We hit a parallel-I/O race in metgrid only after switching to the all-Derecho
  setup he described; reverting to his actual hybrid setup avoids the race.
  Just confirm that the hybrid is intentional and we should match it (which is
  what we've now done) rather than ever trying all-Derecho again.

## Deferred / non-blocking

- **Jeremy's binary updates** — copied from his folder; unclear whether he's pushed
  newer compiles since 2025-06-18. Investigate only if we hit a runtime issue.

- **Clearer placeholder syntax in `namelist.wps.hrrr`** for the date stamps and
  `UM_WRF_1Dom1km` strings on lines 33, 37, 40 — these are runtime placeholders
  the workflow rewrites, but they look like real values. Would document intent
  better; requires understanding which step in `setup_wps_wrf.py` rewrites them.

- **`scripts/alert_usage.sh`** — path now uses `$USER`, but the alert email is
  still `lornjaeger@proton.me`. The script is a manual `while true` loop, not
  auto-run, so it's safe at rest. Update or delete if/when we want quota alerts.

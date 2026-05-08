# wrf-run

WRF (Weather Research and Forecasting) workflow for running historical wildfire
days on NCAR Derecho. Output goes downstream into HDF5 datasets used by
wildfire-spread modelling (wfsts).

## Where to start

- **First time on a new account:** [docs/SETUP.md](docs/SETUP.md) — fresh
  install procedure end-to-end (clone → bin copy → settings → conda env →
  config gen → dry-run → real run).
- **Understanding the workflow:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —
  per-stage breakdown (geogrid / ungrib / metgrid / real / wrf), file map,
  scratch layout.
- **Day-to-day operation:** [run.sh](run.sh) is the queue-throttled multi-day
  driver. Generate per-fire configs with
  `python fires/generate_configs.py`, then launch days with
  `./run.sh --max-days N --max-jobs M <day-indices>...`.

## Per-user configuration

`configs/settings.yaml` (gitignored) holds your `user` and `project`. Templates
under `configs/templates/` use `{{ user }}`, `{{ project }}`, `{{ home_root }}`,
and `{{ scratch_root }}` placeholders rendered into per-fire configs by
`fires/generate_configs.py`. See [docs/SETUP.md §3](docs/SETUP.md#3-create-your-settings-file).

# Psi4 Dashboard

A multi-page [Dash](https://dash.plotly.com/) web app for exploring
[Psi4](https://psicode.org/) benchmark data — timer breakdowns, SCF iteration
counts, and parallel scaling — across Psi4 versions and core counts.

## Pages

| Route           | Page        | What it shows |
| --------------- | ----------- | ------------- |
| `/`             | Home        | Landing page. |
| `/tests`        | Tests       | Per-test line charts of a timer metric (wall/user/system time) across versions. Non-leaf timers expand into a stacked-area breakdown of their child timers. |
| `/timers`       | Timers      | A selected timer's metrics across tests, over versions. |
| `/scf`          | SCF         | Filled-area plots of SCF iterations per label across versions, each with a collapsible per-accelerator breakdown. |
| `/parallelism`  | Parallelism | Wall-time-vs-core-count charts per timer, for a chosen version and test. |

The Tests, Timers, and Parallelism pages share a level slider (to walk the timer
hierarchy), a selection dropdown, and — for the timer pages — a metric tab strip.
Slider position and selections are reflected into the URL query string, so a
shared link restores the view.

## Data

All data is read at startup from a **sibling `psi4dashboard-data` repo**, at the
path hardcoded as `DATA_DIR` in [`data.py`](data.py) (`../psi4dashboard-data/data/`,
relative to where you launch the app). Each loader recursively searches that
directory for its files:

| Dataset       | Source files                     | Grain |
| ------------- | -------------------------------- | ----- |
| timing        | `timer.json`                     | one row per timer per test run |
| scf           | `scf_iterations.json`            | one row per (test run, SCF label) |
| parallelism   | `<test>.json.n<cores>.out`       | one row per timer per core count |

Malformed or empty source files are skipped; if every file for a dataset is
skipped, that dataset loads as an empty frame (the app still starts). See the
module docstring and `create_*_df` parsers in [`data.py`](data.py) for the full
per-column schemas.

## Layout

```
dashboard.py     App entry point: loads the datasets and builds/runs the Dash app.
data.py          Data loading, parsing, and runtime state (module-global DataFrames).
callbacks.py     Callback logic and chart-building helpers shared across pages.
components.py    Reusable Dash layout builders (slider, dropdown, tabs, chart grid).
theme.py         Shared Plotly dark-theme styling.
pages/           One module per route (home, tests, timers, scf, parallelism).
assets/          CSS served automatically by Dash.
```

## Requirements

- Python 3
- `dash`, `plotly`, `pandas`, `packaging`

Install into a fresh virtual environment or conda environment, e.g.:

```bash
pip install dash plotly pandas packaging
```

## Running

Check out the `psi4dashboard-data` repo alongside this one so that
`../psi4dashboard-data/data/` resolves, then from the project root:

```bash
# Defaults to Dash's built-in host/port (http://127.0.0.1:8050)
python dashboard.py

# Or bind an explicit address
python dashboard.py --address 127.0.0.1:8050
```

The app runs with `debug=True`, so it hot-reloads on source changes.

## License

Released under [CC0 1.0 Universal](LICENSE) (public domain dedication).

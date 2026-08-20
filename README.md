# F1 Data Pipeline to Power BI Dashboard

This project pulls Formula 1 data from the free, open
[f1api.dev](https://f1api.dev) API, transforms the nested JSON responses into
tabular data, stores the result in SQLite, and exposes that database to Power BI.

The pipeline supports multi-season incremental loads, derived analytics tables,
structured run summaries, automated GitHub Actions refreshes, linting/type
checks, tests, and Docker-based execution.

## Project Structure

```text
f1-powerbi-project/
├── .github/workflows/
│   ├── quality.yml          # PR/push lint, type check, and tests
│   └── update-data.yml      # scheduled/manual data refresh
├── config/
│   ├── __init__.py
│   └── settings.py          # loads config.yaml and exposes paths/settings
├── docs/
│   └── powerbi.md           # relationship map + DAX measures for Power BI
├── scripts/
│   └── refresh.ps1          # one-command refresh (Windows)
├── src/
│   ├── __init__.py
│   ├── analytics.py         # derived metrics written to analytics tables
│   ├── api_client.py        # f1api.dev client with retries and errors
│   ├── data_processor.py    # JSON-to-DataFrame transformations
│   ├── database.py          # SQLite schema and upsert helpers
│   ├── fetch_data.py        # pipeline orchestration
│   └── run_summary.py       # logs/run_summary.json writer
├── data/
│   ├── raw/                 # optional raw JSON debug files
│   ├── processed/           # optional CSV exports
│   └── f1.db                # SQLite output for Power BI
├── logs/
│   └── run_summary.json     # latest structured run summary
├── tests/
├── app.py                   # Streamlit preview of data/f1.db
├── Dockerfile
├── Makefile                 # one-command refresh (macOS/Linux)
├── pyproject.toml
├── config.yaml
└── main.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

For runtime-only installs, use:

```bash
python -m pip install -e .
```

## Running The Pipeline

```bash
python main.py
```

Useful options:

```bash
python main.py --season 2024
python main.py --start-year 2020 --end-year 2024
python main.py --end-year current
python main.py --force-refresh      # re-fetch every season, even complete ones
python main.py --no-race-results
python main.py --export-csv
python main.py --verbose
```

The main output is `data/f1.db`. The latest structured execution summary is
written to `logs/run_summary.json`.

By default, seasons already fully loaded in the database are skipped, so a
routine refresh only fetches the live season (much faster). Race results for
the last two rounds of a season are always re-fetched so post-race penalties
and corrections reach Power BI. Use `--force-refresh` to rebuild everything.

## Web Preview (Streamlit)

No Power BI handy? Preview the database in a browser:

```bash
streamlit run app.py
```

The app has five tabs, all reading directly from `data/f1.db`:

- **Season Hub** — championship metrics (leader, gap to 2nd, most wins/podiums,
  constructor leader) plus team-colored driver and constructor standings.
- **Points Trend** — cumulative points per driver with an avg-points-per-race
  toggle and a top-N selector.
- **Race Positions** — a driver × round finish-position heatmap plus rolling
  average position and recent-form charts.
- **Teammate H2H** — head-to-head record and points-advantage per round for any
  team, with a season points comparison.
- **Race Results** — pick any round for a grid-vs-finish chart, points scored,
  and the full results table.

Every chart is color-coded by team (F1 broadcast style) and every tab has a CSV
download button. Requires `streamlit` (installed with `.[dev]`).

## Power BI Guide

See `docs/powerbi.md` for the table relationship map and ready-to-paste DAX
measures (wins, average finish, H2H record, data freshness card).

## Configuration

Runtime settings live in `config.yaml`:

```yaml
api:
  base_url: "https://f1api.dev/api"
  request_timeout: 15
  request_delay: 0.5
  max_retries: 3

seasons:
  start_year: 2018
  end_year: current

pipeline:
  fetch_race_results: true
  save_raw_json: true
  export_csv: false
```

CLI arguments override the config file for a single run.

## Database Tables

Core tables:

- `drivers`
- `teams`
- `circuits`
- `races`
- `race_results`
- `driver_standings`
- `constructor_standings`

Analytics tables:

- `analytics_points_trend`
- `analytics_rolling_position`
- `analytics_recent_form`
- `analytics_teammate_comparison`

Metadata:

- `pipeline_meta` — key/value JSON of the latest run (`finished_at`,
  `duration_seconds`, `seasons`, `error_count`) for "data as of" reporting.

Power BI should connect to `data/f1.db` and can infer most relationships from
the schema foreign keys.

## Automation

`.github/workflows/update-data.yml` runs on a weekly schedule and can also be
started manually from the GitHub Actions UI with `workflow_dispatch`.

The workflow:

1. Checks out the repo.
2. Installs the project with dev dependencies.
3. Runs Ruff formatting checks and linting.
4. Runs mypy.
5. Runs pytest.
6. Executes `python main.py`.
7. Commits `data/f1.db` and `logs/run_summary.json` back to the same branch if
   either file changed.

The workflow uses the built-in `GITHUB_TOKEN`. It needs:

```yaml
permissions:
  contents: write
```

Repository settings must allow GitHub Actions to write to the repository. If the
branch is protected, allow the workflow/bot to push or route updates through a
pull request instead.

## Linting, Formatting, Type Checks, And Tests

Run the same quality gates locally:

```bash
ruff format --check .
ruff check .
mypy config src main.py
pytest
```

To auto-format:

```bash
ruff format .
```

Or use the one-command refresh (lint + type check + test + pipeline):

```bash
make refresh        # macOS/Linux
.\scripts\refresh.ps1   # Windows PowerShell
```

`.github/workflows/quality.yml` runs the quality gates on pull requests and on
pushes to `main`.

## Docker

Build the image:

```bash
docker build -t f1-powerbi-pipeline .
```

Run the pipeline inside the container:

```bash
docker run --rm f1-powerbi-pipeline
```

To persist generated outputs to the local checkout:

```bash
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/logs:/app/logs" f1-powerbi-pipeline
```

On Windows PowerShell:

```powershell
docker run --rm -v "${PWD}\data:/app/data" -v "${PWD}\logs:/app/logs" f1-powerbi-pipeline
```

Docker is not required by the scheduled GitHub Actions workflow; the workflow
runs Python directly for faster setup. The Dockerfile is useful for local
repeatability or for moving the pipeline to another scheduler later.

## Notes For Power BI

Connect Power BI to `data/f1.db` using a SQLite connector. Refresh Power BI
after the pipeline runs locally, in Docker, or through GitHub Actions.

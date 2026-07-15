# F1 Data Pipeline → Power BI Dashboard

A project that pulls Formula 1 data from the free,
open [f1api.dev](https://f1api.dev) API using Python, cleans it into a
SQLite star schema, and hands it off to Power BI for an interactive dashboard.

## What this project does

- Making HTTP requests to a real REST API (`requests`)
- Handling retries, timeouts, and errors gracefully
- Turning nested JSON into clean tabular data (`pandas`)
- Storing data in a Power BI-friendly SQLite star schema
- Incrementally loading multi-season historical data
- Structuring a Python project so it's readable and maintainable

## Project structure

```
f1-powerbi-project/
├── config.yaml              # tunables: season range, API settings, pipeline flags
├── config/
│   └── settings.py          # loads config.yaml; exposes paths and helpers
├── src/
│   ├── api_client.py        # talks to f1api.dev — the ONLY file that does
│   ├── data_processor.py    # flattens JSON responses into DataFrames
│   ├── database.py          # SQLite star schema + upsert/incremental helpers
│   └── fetch_data.py        # orchestrates: fetch -> process -> save to DB
├── data/
│   ├── raw/                 # raw JSON dumps (debugging aid, gitignored)
│   ├── processed/           # optional legacy CSV export (--export-csv)
│   └── f1.db                # SQLite database — primary output for Power BI
├── powerbi/
│   └── SETUP_GUIDE.md       # connecting Power BI to the data source
├── main.py                  # entry point — run this
├── requirements.txt
└── .gitignore
```

Each piece has one job. If something about the API changes, you touch
`api_client.py`. If a column looks wrong in Power BI, you touch
`data_processor.py`. Schema or load logic changes go in `database.py` /
`fetch_data.py`.

## Setup

1. **Clone / open this folder**, then create a virtual environment (optional
   but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   ```
2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```
3. **Run the pipeline:**

   ```bash
   python main.py
   ```

   On first run this builds `data/f1.db` from your configured season range.
   Subsequent runs only fetch data that is not already in the database.
4. **Open Power BI** and connect to `data/f1.db` (see schema below).

## Configuration (`config.yaml`)

All tunables live in `config.yaml` at the project root. CLI flags override
these values when provided.

```yaml
api:
  base_url: "https://f1api.dev/api"
  request_timeout: 15
  request_delay: 0.5
  max_retries: 3

seasons:
  start_year: 2018
  end_year: current   # "current" appends the live season after historical years

pipeline:
  fetch_race_results: true
  save_raw_json: true
  export_csv: false   # set true to also write data/processed/*.csv
```

**Season range behaviour**

| Setting | Result |
|---------|--------|
| `start_year: 2018`, `end_year: 2025` | Fetches 2018, 2019, …, 2025 |
| `end_year: current` | Fetches 2018 … (calendar year − 1), then `current` |
| `--season 2023` | Single season only; ignores the config range |
| `--start-year 2020 --end-year 2024` | Overrides config range |

## CLI options

```bash
python main.py                                    # config.yaml season range
python main.py --season 2023                      # single season
python main.py --start-year 2020 --end-year 2024  # custom range
python main.py --end-year current                 # through last year + current
python main.py --no-race-results                  # skip per-race results
python main.py --export-csv                       # also write legacy CSV files
python main.py --verbose                          # debug logging
```

## Database schema (star schema)

Primary output: **`data/f1.db`**

### Dimension tables

| Table | Primary key | Description |
|-------|-------------|-------------|
| `drivers` | `driver_id` | Driver master data (name, nationality, number) |
| `teams` | `team_id` | Constructor master data |
| `circuits` | `circuit_id` | Circuit name, city, country |
| `races` | `(season, round)` | Race calendar; FK → `circuits.circuit_id` |

### Fact table

| Table | Primary key | Foreign keys | Measures |
|-------|-------------|--------------|----------|
| `race_results` | `(season, round, driver_id)` | → `races`, `drivers`, `teams` | `position`, `grid`, `points`, `time`, `finished`, `retired` |

### Supplementary tables (not core star schema, but useful in reports)

| Table | Primary key |
|-------|-------------|
| `driver_standings` | `(season, driver_id)` |
| `constructor_standings` | `(season, team_id)` |

**Power BI relationships** (auto-detected by the SQLite connector):

```
circuits ──< races ──< race_results >── drivers
                              └──> teams
drivers ──< driver_standings
teams   ──< constructor_standings
```

Column names are prefixed by role (`driver_id`, `team_id`, `circuit_id`) so
there are no ambiguous joins.

## Incremental loading

The pipeline avoids re-fetching data that is already stored:

1. **Race results** — before each `/{year}/{round}/race` call, the pipeline
   checks `race_results` for that `(season, round)`. If rows exist, the round
   is skipped.
2. **Current season** — standings and dimension tables are refreshed every
   run (they change as the season progresses). Race results use the same
   incremental check, so newly completed rounds are picked up automatically.
3. **Historical seasons** — once all rounds for a year are in the database,
   re-running skips those API calls entirely.

Re-running `python main.py` is safe: it is an incremental sync, not a full
refresh.

## Connecting Power BI

1. **Get data** → **Database** → **SQLite database**
2. Point to `data/f1.db` in this project folder
3. Select the tables you need; Power BI should infer the relationships above
4. Refresh the dataset after running `python main.py`

Legacy CSV export is still available via `export_csv: true` in `config.yaml`
or `--export-csv` on the command line.

## Troubleshooting API field names

This project is wired up against f1api.dev's documented endpoint shape (see
[f1api.dev/docs](https://f1api.dev/docs)). If a table comes out empty:

1. Open the matching raw JSON file in `data/raw/`
2. Compare field names against `src/data_processor.py`
3. Adjust the `.get(...)` calls there — everything else stays unchanged

## Phase roadmap

- **Phase 1 (this release):** SQLite star schema, multi-season incremental load, config file
- **Phase 2:** (planned) tests, CI/CD, Docker
- **Phase 3:** (planned) analytics layer

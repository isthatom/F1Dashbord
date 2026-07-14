# F1 Data Pipeline → Power BI Dashboard

A beginner-friendly project that pulls Formula 1 data from the free,
open [f1api.dev](https://f1api.dev) API using Python, cleans it into flat
CSV tables, and hands them off to Power BI for an interactive dashboard.

No API key, no authentication — the API is free and open.

## What this project teaches

- Making HTTP requests to a real REST API (`requests`)
- Handling retries, timeouts, and errors gracefully
- Turning nested JSON into clean tabular data (`pandas`)
- Structuring a Python project so it's readable and maintainable
- Feeding processed data into Power BI for visualization

## Project structure

```
f1-powerbi-project/
├── config/
│   └── settings.py          # all settings: API URL, season, folder paths
├── src/
│   ├── api_client.py        # talks to f1api.dev — the ONLY file that does
│   ├── data_processor.py    # flattens JSON responses into DataFrames
│   └── fetch_data.py        # orchestrates: fetch -> process -> save
├── data/
│   ├── raw/                 # raw JSON dumps (debugging aid, gitignored)
│   └── processed/           # clean CSVs — this is what Power BI reads
├── powerbi/
│   └── SETUP_GUIDE.md       # step-by-step: connecting Power BI to the CSVs
├── main.py                  # entry point — run this
├── requirements.txt
└── .gitignore
```

Each piece has one job. If something about the API changes, you touch
`api_client.py`. If a column looks wrong in Power BI, you touch
`data_processor.py`. `main.py` never needs to change for either of those.

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

   You'll see log lines as it fetches drivers, teams, races, standings, and
   race results, then writes CSVs to `data/processed/`.

4. **Open Power BI** and follow `powerbi/SETUP_GUIDE.md` to load the CSVs
   and build the dashboard.

## CLI options

```bash
python main.py --season 2023         # pull a specific season instead of current
python main.py --no-race-results     # skip per-race results (fewer API calls)
python main.py --verbose             # see detailed debug logs
```

## A note on API endpoint paths

This project is wired up against f1api.dev's documented endpoint shape
(`/api/{season}/drivers`, `/api/{season}/drivers-championship`, etc. — see
[f1api.dev/docs](https://f1api.dev/docs)). APIs occasionally tweak field
names or paths. If you run `python main.py` and a CSV comes out empty or a
column is blank:

1. Open the matching raw JSON file in `data/raw/` and look at the actual
   field names the API returned.
2. Compare against the `.get(...)` calls in `src/data_processor.py`.
3. Adjust the key names there — everything else in the project is
   unaffected.

This is completely normal when wiring up any real-world API for the first
time, not a sign the project is broken.

## Next steps (once this works end-to-end)

- **Automate it**: schedule `python main.py` to run weekly (cron / Windows
  Task Scheduler / a GitHub Action) so your CSVs — and Power BI dashboard —
  refresh automatically after each race weekend.
- **Add more seasons**: loop `main.py` over a list of years to build a
  historical dataset and compare eras.
- **Push to GitHub**: commit the `data/processed/*.csv` files too, so
  anyone (including recruiters) can open the repo and see real output
  without having to run anything.

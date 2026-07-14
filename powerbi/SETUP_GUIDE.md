# Connecting Power BI to this project

Once you've run `python main.py` at least once, you'll have CSVs sitting in
`data/processed/`:

- `drivers.csv`
- `teams.csv`
- `races.csv`
- `driver_standings.csv`
- `constructor_standings.csv`
- `race_results.csv`

Power BI just needs to read these. No API, no auth, nothing fancy.

## 1. Import the data

1. Open Power BI Desktop → **Get Data** → **Text/CSV**.
2. Navigate to `data/processed/` and select `driver_standings.csv`.
3. Click **Transform Data** (not "Load" directly) so you land in Power Query
   — this lets you check column types before loading.
4. Repeat **Get Data → Text/CSV** for the other CSVs you want
   (`teams.csv`, `races.csv`, `race_results.csv`, etc.).
5. In Power Query, confirm:
   - `points`, `position`, `wins`, `round` are typed as **Whole Number** / **Decimal**
   - `schedule_date` / `birthday` are typed as **Date**
6. Click **Close & Apply**.

## 2. Build relationships

In the **Model** view, drag to connect:

- `driver_standings.driver_id` → `drivers.driver_id`
- `race_results.driver_id` → `drivers.driver_id`
- `race_results.round` → `races.round`
- `constructor_standings.team_id` → `teams.team_id`

This lets you slice points/results by driver nationality, team, or circuit
without duplicating columns everywhere.

## 3. Suggested first visuals

- **Bar chart**: `driver_standings` — driver_name vs points, sorted descending
  (instant championship leaderboard).
- **Line chart**: cumulative points per driver across `race_results.round`
  (shows the championship battle unfolding race by race — you'll want a
  running-total measure in DAX for this, e.g.
  `Cumulative Points = CALCULATE(SUM(race_results[points]), FILTER(ALL(race_results[round]), race_results[round] <= MAX(race_results[round])))`).
- **Map**: `races` — circuit city/country, sized by something like laps or
  just as markers on the calendar.
- **Table**: `constructor_standings` for a clean team leaderboard.
- **Slicer**: `season` — useful once you start pulling more than one season.

## 4. Refreshing data

Every time you want new data (e.g. after a race weekend):

```bash
python main.py --season current
```

Then in Power BI: **Home → Refresh**. Since the CSVs live at fixed paths,
Power BI will just pick up the new rows — no need to re-point the data
source.

If you want this to happen automatically, see the "next step" idea in the
main README about scheduling the script.

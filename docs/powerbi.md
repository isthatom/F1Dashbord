# Power BI Guide

Connect Power BI to `data/f1.db` with a SQLite connector, then use the map below.

## Table Relationships

| From | To | Keys |
|------|----|------|
| `race_results` (fact) | `races` | `season`, `round` |
| `race_results` | `drivers` | `driver_id` |
| `race_results` | `teams` | `team_id` |
| `races` | `circuits` | `circuit_id` |
| `driver_standings` | `drivers` | `driver_id` |
| `driver_standings` | `teams` | `team_id` |
| `constructor_standings` | `teams` | `team_id` |
| `analytics_*` tables | `drivers` / `teams` | `driver_id` / `team_id` |

The Power BI SQLite connector usually auto-detects these from the schema
foreign keys. If not, add them manually with a single-direction filter
(`1:*` from dimensions to facts).

## Ready-Made DAX Measures

```dax
// Total race wins for a driver (any season selected)
Total Wins =
    CALCULATE(
        COUNTROWS(race_results),
        race_results[position] = 1
    )

// Average finishing position for finished races
Avg Finish =
    AVERAGE(race_results[position])

// Championship points per race (normalized across seasons)
Points Per Race =
    DIVIDE(
        SUM(race_results[points]),
        DISTINCTCOUNT(race_results[round])
    )

// Driver vs teammate H2H record (wins in points advantage)
H2H Lead Races =
    CALCULATE(
        COUNTROWS(analytics_teammate_comparison),
        analytics_teammate_comparison[points_advantage] > 0
    )

// Data freshness card: last pipeline run time
Last Updated =
    VAR Raw = LOOKUPVALUE(pipeline_meta[value], pipeline_meta[key], "finished_at")
    RETURN
        VALUE(Raw)

// Current season flag on races
Is Current Season =
    VAR MaxSeason = MAX(races[season])
    RETURN
        IF(races[season] = MaxSeason, "Current", "Historical")
```

## Notes

- `position` in `race_results` is `NULL` for DNF/NC/DSQ rows; filter
  `finished = 1` before averaging positions.
- The `analytics_*` tables are fully recomputed on every pipeline run.
- `pipeline_meta` holds JSON blobs: `finished_at`, `duration_seconds`,
  `seasons`, `error_count`. Wrap them in `VALUE()`/`JSON.FIND` as needed.
- Race results for the last two rounds of each season are always re-fetched,
  so post-race penalties appear after a refresh. Historical corrections need
  `python main.py --force-refresh`.
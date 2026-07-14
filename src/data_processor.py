"""
Turns raw JSON from the API into clean, flat pandas DataFrames that Power BI
will be happy to import.

APIs usually return nested JSON (objects inside objects). Power BI, Excel,
and most charting tools want flat tables: one row per record, one column
per field. This module is where that flattening happens, and it's the
first place to look if a column looks wrong once you're in Power BI.

NOTE: the exact key names below (e.g. "drivers", "driverId", "team") are
based on f1api.dev's documented response shape. If the live API returns
slightly different field names, run `python main.py --season current`
once, inspect the JSON written to data/raw/, and adjust the `.get(...)`
calls here to match — that's the normal workflow when wiring up any new
API, not a sign something is broken.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def drivers_to_df(raw: dict) -> pd.DataFrame:
    """Flatten the /drivers response into one row per driver."""
    records = raw.get("drivers", raw if isinstance(raw, list) else [])
    rows = []
    for d in records:
        rows.append({
            "driver_id": d.get("driverId"),
            "full_name": f"{d.get('name', '')} {d.get('surname', '')}".strip(),
            "nationality": d.get("nationality"),
            "birthday": d.get("birthday"),
            "number": d.get("number"),
            "shortname": d.get("shortName"),
            "team": d.get("teamId") or d.get("team"),
        })
    return pd.DataFrame(rows)


def teams_to_df(raw: dict) -> pd.DataFrame:
    """Flatten the /teams response into one row per constructor."""
    records = raw.get("teams", raw if isinstance(raw, list) else [])
    rows = []
    for t in records:
        rows.append({
            "team_id": t.get("teamId"),
            "team_name": t.get("teamName") or t.get("name"),
            "nationality": t.get("teamNationality") or t.get("nationality"),
            "first_appearance": t.get("firstAppeareance") or t.get("firstAppearance"),
            "constructors_championships": t.get("constructorsChampionships"),
            "drivers_championships": t.get("driversChampionships"),
        })
    return pd.DataFrame(rows)


def races_to_df(raw: dict) -> pd.DataFrame:
    """
    Flatten the races-calendar response into one row per race.

    Quirk of this API: GET /api/{year} returns the list under the key
    "races", while GET /api/current returns it under "race" (singular).
    We just check both.
    """
    records = raw.get("races") or raw.get("race") or (raw if isinstance(raw, list) else [])
    rows = []
    for r in records:
        circuit = r.get("circuit", {}) or {}
        schedule = r.get("schedule", {}) or {}
        race_date = (schedule.get("race", {}) or {}).get("date") if schedule else r.get("date")
        rows.append({
            "round": r.get("round"),
            "race_id": r.get("raceId"),
            "race_name": r.get("raceName") or r.get("name"),
            "race_date": race_date,
            "circuit_id": circuit.get("circuitId"),
            "circuit_name": circuit.get("circuitName"),
            "city": circuit.get("city"),
            "country": circuit.get("country"),
        })
    return pd.DataFrame(rows)


def driver_standings_to_df(raw: dict, season: str) -> pd.DataFrame:
    """Flatten the drivers' championship standings."""
    records = raw.get("drivers_championship", raw.get("standings", []))
    rows = []
    for entry in records:
        driver = entry.get("driver", {}) or {}
        team = entry.get("team", {}) or {}
        rows.append({
            "season": season,
            "position": entry.get("position"),
            "driver_id": driver.get("driverId"),
            "driver_name": f"{driver.get('name', '')} {driver.get('surname', '')}".strip(),
            "team_name": team.get("teamName") or team.get("name"),
            "points": entry.get("points"),
            "wins": entry.get("wins"),
        })
    return pd.DataFrame(rows)


def constructor_standings_to_df(raw: dict, season: str) -> pd.DataFrame:
    """Flatten the constructors' championship standings."""
    records = raw.get("constructors_championship", raw.get("standings", []))
    rows = []
    for entry in records:
        team = entry.get("team", {}) or {}
        rows.append({
            "season": season,
            "position": entry.get("position"),
            "team_id": team.get("teamId"),
            "team_name": team.get("teamName") or team.get("name"),
            "points": entry.get("points"),
            "wins": entry.get("wins"),
        })
    return pd.DataFrame(rows)


def race_results_to_df(raw: dict, season: str, round_number: int) -> pd.DataFrame:
    """
    Flatten a single race's results into one row per finishing driver.

    The API nests the actual result list two levels deep:
    { "races": { "raceName": ..., "results": [ {...}, {...} ] } }
    """
    race = raw.get("races", {}) or {}
    records = race.get("results", [])
    rows = []
    for entry in records:
        driver = entry.get("driver", {}) or {}
        team = entry.get("team", {}) or {}
        rows.append({
            "season": season,
            "round": round_number,
            "race_name": race.get("raceName"),
            "position": entry.get("position"),
            "driver_id": driver.get("driverId"),
            "driver_name": f"{driver.get('name', '')} {driver.get('surname', '')}".strip(),
            "team_name": team.get("teamName") or team.get("name"),
            "grid": entry.get("grid"),
            "points": entry.get("points"),
            "time": entry.get("time"),
            "retired": entry.get("retired"),
        })
    return pd.DataFrame(rows)

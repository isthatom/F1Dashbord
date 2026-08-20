"""
Flatten nested f1api.dev JSON responses into pandas DataFrames.

This is the ONLY module that knows how API field names map to table columns.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DRIVER_COLUMNS = [
    "driver_id",
    "full_name",
    "nationality",
    "birthday",
    "number",
    "shortname",
    "team_id",
]
RACE_RESULT_COLUMNS = [
    "season",
    "round",
    "race_name",
    "position",
    "finished",
    "driver_id",
    "driver_name",
    "team_id",
    "team_name",
    "grid",
    "points",
    "time",
    "retired",
]


NON_FINISH_POSITIONS = {"NC", "DSQ", "DNS", "DNQ"}


def _dataframe_from_rows(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    """Create a DataFrame while preserving explicit None values."""
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns, dtype=object)


def circuits_to_df(raw: dict[str, Any]) -> pd.DataFrame:
    """Flatten the /circuits response into one row per circuit."""
    records = raw.get("circuits", raw if isinstance(raw, list) else [])
    rows = []
    for c in records:
        rows.append(
            {
                "circuit_id": c.get("circuitId"),
                "circuit_name": c.get("circuitName") or c.get("name"),
                "city": c.get("city"),
                "country": c.get("country"),
            }
        )
    return _dataframe_from_rows(
        rows,
        ["circuit_id", "circuit_name", "city", "country"],
    )


def drivers_to_df(raw: dict[str, Any]) -> pd.DataFrame:
    """Flatten the /drivers response into one row per driver."""
    records = raw.get("drivers", raw if isinstance(raw, list) else [])
    rows = []
    for d in records:
        rows.append(
            {
                "driver_id": d.get("driverId"),
                "full_name": f"{d.get('name', '')} {d.get('surname', '')}".strip(),
                "nationality": d.get("nationality"),
                "birthday": d.get("birthday"),
                "number": d.get("number"),
                "shortname": d.get("shortName"),
                "team_id": d.get("teamId") or d.get("team"),
            }
        )
    return _dataframe_from_rows(rows, DRIVER_COLUMNS)


def teams_to_df(raw: dict[str, Any]) -> pd.DataFrame:
    """Flatten the /teams response into one row per constructor."""
    records = raw.get("teams", raw if isinstance(raw, list) else [])
    rows = []
    for t in records:
        rows.append(
            {
                "team_id": t.get("teamId"),
                "team_name": t.get("teamName") or t.get("name"),
                "nationality": t.get("teamNationality") or t.get("nationality"),
                "first_appearance": t.get("firstAppeareance") or t.get("firstAppearance"),
                "constructors_championships": t.get("constructorsChampionships"),
                "drivers_championships": t.get("driversChampionships"),
            }
        )
    return _dataframe_from_rows(
        rows,
        [
            "team_id",
            "team_name",
            "nationality",
            "first_appearance",
            "constructors_championships",
            "drivers_championships",
        ],
    )


def races_to_df(raw: dict[str, Any], season: str | int | None = None) -> pd.DataFrame:
    """
    Flatten the races-calendar response into one row per race.

    Quirk of this API: GET /api/{year} returns the list under the key
    "races", while GET /api/current returns it under "race" (singular).
    We just check both.
    """
    records = raw.get("races") or raw.get("race") or (raw if isinstance(raw, list) else [])
    resolved_season = season if season is not None else raw.get("season")
    rows = []
    for r in records:
        circuit = r.get("circuit", {}) or {}
        schedule = r.get("schedule", {}) or {}
        race_date = (schedule.get("race", {}) or {}).get("date") if schedule else r.get("date")
        rows.append(
            {
                "season": resolved_season,
                "round": r.get("round"),
                "race_id": r.get("raceId"),
                "race_name": r.get("raceName") or r.get("name"),
                "race_date": race_date,
                "circuit_id": circuit.get("circuitId"),
                "circuit_name": circuit.get("circuitName"),
                "city": circuit.get("city"),
                "country": circuit.get("country"),
            }
        )
    return _dataframe_from_rows(
        rows,
        [
            "season",
            "round",
            "race_id",
            "race_name",
            "race_date",
            "circuit_id",
            "circuit_name",
            "city",
            "country",
        ],
    )


def circuits_from_races_df(races_df: pd.DataFrame) -> pd.DataFrame:
    """Extract a circuits dimension from an already-flattened races DataFrame."""
    if races_df.empty:
        return pd.DataFrame(columns=["circuit_id", "circuit_name", "city", "country"])
    return (
        races_df[["circuit_id", "circuit_name", "city", "country"]]
        .dropna(subset=["circuit_id"])
        .drop_duplicates("circuit_id")
    )


def driver_standings_to_df(raw: dict[str, Any], season: str | int) -> pd.DataFrame:
    """Flatten the drivers' championship standings."""
    records = raw.get("drivers_championship", raw.get("standings", []))
    rows = []
    for entry in records:
        driver = entry.get("driver", {}) or {}
        team = entry.get("team", {}) or {}
        rows.append(
            {
                "season": int(season),
                "position": entry.get("position"),
                "driver_id": entry.get("driverId") or driver.get("driverId"),
                "driver_name": f"{driver.get('name', '')} {driver.get('surname', '')}".strip(),
                "team_id": entry.get("teamId") or team.get("teamId"),
                "team_name": team.get("teamName") or team.get("name"),
                "points": entry.get("points"),
                "wins": entry.get("wins"),
            }
        )
    return _dataframe_from_rows(
        rows,
        [
            "season",
            "position",
            "driver_id",
            "driver_name",
            "team_id",
            "team_name",
            "points",
            "wins",
        ],
    )


def constructor_standings_to_df(raw: dict[str, Any], season: str | int) -> pd.DataFrame:
    """Flatten the constructors' championship standings."""
    records = raw.get("constructors_championship", raw.get("standings", []))
    rows = []
    for entry in records:
        team = entry.get("team", {}) or {}
        rows.append(
            {
                "season": int(season),
                "position": entry.get("position"),
                "team_id": entry.get("teamId") or team.get("teamId"),
                "team_name": team.get("teamName") or team.get("name"),
                "points": entry.get("points"),
                "wins": entry.get("wins"),
            }
        )
    return _dataframe_from_rows(
        rows,
        ["season", "position", "team_id", "team_name", "points", "wins"],
    )


def race_results_to_df(
    raw: dict[str, Any],
    season: str | int,
    round_number: int,
) -> pd.DataFrame:
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
        position = entry.get("position")
        rows.append(
            {
                "season": int(season),
                "round": round_number,
                "race_name": race.get("raceName"),
                "position": position,
                "finished": (
                    0 if position is None or str(position).upper() in NON_FINISH_POSITIONS else 1
                ),
                "driver_id": driver.get("driverId"),
                "driver_name": f"{driver.get('name', '')} {driver.get('surname', '')}".strip(),
                "team_id": team.get("teamId"),
                "team_name": team.get("teamName") or team.get("name"),
                "grid": entry.get("grid"),
                "points": entry.get("points"),
                "time": entry.get("time"),
                "retired": entry.get("retired"),
            }
        )
    df = _dataframe_from_rows(rows, RACE_RESULT_COLUMNS)
    df["position"] = pd.to_numeric(df["position"], errors="coerce")
    return df

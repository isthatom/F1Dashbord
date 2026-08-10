"""
Derived metrics computed from race_results for Power BI reporting.

Each function is a pure transformation (DataFrame in → DataFrame out) so the
logic is easy to unit-test.  run_analytics() reads from f1.db, computes all
metrics, and writes them back as dedicated analytics tables.
"""

import logging
from typing import Any

import pandas as pd

from src.database import F1Database

logger = logging.getLogger(__name__)

ROLLING_WINDOW = 5


def compute_points_trend(race_results: pd.DataFrame) -> pd.DataFrame:
    """
    Points-per-race trend per driver across each season.

    Columns: season, round, driver_id, race_points, cumulative_points,
             season_avg_points_per_race
    """
    if race_results.empty:
        return _empty_points_trend()

    df = race_results[["season", "round", "driver_id", "points"]].copy()
    df["race_points"] = df["points"].fillna(0)
    df = df.sort_values(["season", "driver_id", "round"])

    df["cumulative_points"] = df.groupby(["season", "driver_id"])["race_points"].cumsum()
    df["races_completed"] = df.groupby(["season", "driver_id"]).cumcount() + 1
    df["season_avg_points_per_race"] = df["cumulative_points"] / df["races_completed"]

    return df[
        [
            "season",
            "round",
            "driver_id",
            "race_points",
            "cumulative_points",
            "season_avg_points_per_race",
        ]
    ]


def compute_rolling_position(
    race_results: pd.DataFrame,
    window: int = ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    Rolling average finishing position over the last *window* races.

    Only finished races (finished == 1 with a numeric position) count toward
    the average.  DNFs/NCs are excluded from the window, not penalised as a
    high number.
    """
    if race_results.empty:
        return _empty_rolling_position()

    df = race_results[["season", "round", "driver_id", "finished", "position"]].copy()
    df = df.sort_values(["season", "driver_id", "round"])
    df["finished_position"] = df["position"].where(df["finished"] == 1)

    df["rolling_avg_position"] = (
        df.groupby(["season", "driver_id"])["finished_position"]
        .transform(lambda s: s.rolling(window=window, min_periods=1).mean())
    )
    df["races_in_window"] = (
        df.groupby(["season", "driver_id"])["finished_position"]
        .transform(lambda s: s.rolling(window=window, min_periods=1).count())
    )

    return df[
        ["season", "round", "driver_id", "rolling_avg_position", "races_in_window"]
    ]


def compute_recent_form(
    race_results: pd.DataFrame,
    window: int = ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    Points scored in the last *window* races (recent form).

    DNFs contribute 0 points but still count as a race in the window.
    """
    if race_results.empty:
        return _empty_recent_form()

    df = race_results[["season", "round", "driver_id", "points"]].copy()
    df["race_points"] = df["points"].fillna(0)
    df = df.sort_values(["season", "driver_id", "round"])

    df["recent_form_points"] = (
        df.groupby(["season", "driver_id"])["race_points"]
        .transform(lambda s: s.rolling(window=window, min_periods=1).sum())
    )
    df["races_in_window"] = (
        df.groupby(["season", "driver_id"])["race_points"]
        .transform(lambda s: s.rolling(window=window, min_periods=1).count())
    )

    return df[["season", "round", "driver_id", "recent_form_points", "races_in_window"]]


def compute_teammate_comparison(race_results: pd.DataFrame) -> pd.DataFrame:
    """
    Head-to-head teammate comparison for each race.

    One row per driver who had a teammate in the same (season, round, team).
    position_advantage: positive means this driver finished ahead of teammate.
    points_advantage: this driver's points minus teammate's points.
    """
    if race_results.empty:
        return _empty_teammate_comparison()

    cols = ["season", "round", "team_id", "driver_id", "position", "points"]
    df = race_results[cols].copy()
    df["points"] = df["points"].fillna(0)

    rows = []
    for (_, _, _team_id), group in df.groupby(["season", "round", "team_id"]):
        drivers = group.dropna(subset=["driver_id"]).reset_index(drop=True)
        if len(drivers) != 2:
            continue

        a, b = drivers.iloc[0], drivers.iloc[1]
        rows.append(_teammate_row(a, b))
        rows.append(_teammate_row(b, a))

    if not rows:
        return _empty_teammate_comparison()

    return pd.DataFrame(rows)


def _teammate_row(driver: pd.Series, teammate: pd.Series) -> dict[str, Any]:
    pos_adv = None
    if pd.notna(driver["position"]) and pd.notna(teammate["position"]):
        pos_adv = float(teammate["position"]) - float(driver["position"])

    return {
        "season": int(driver["season"]),
        "round": int(driver["round"]),
        "team_id": driver["team_id"],
        "driver_id": driver["driver_id"],
        "teammate_driver_id": teammate["driver_id"],
        "driver_points": float(driver["points"]),
        "teammate_points": float(teammate["points"]),
        "points_advantage": float(driver["points"]) - float(teammate["points"]),
        "position_advantage": pos_adv,
    }


def run_analytics(db: F1Database | None = None) -> dict[str, int]:
    """
    Recompute all analytics tables from race_results and persist to f1.db.

    Returns a dict of table_name → row_count for the run summary.
    """
    db = db or F1Database()
    race_results = db.read_race_results()
    rolling_position = compute_rolling_position(race_results)
    if not race_results.empty:
        finished_keys = race_results.loc[
            race_results["finished"] == 1,
            ["season", "round", "driver_id"],
        ]
        rolling_position = rolling_position.merge(
            finished_keys,
            on=["season", "round", "driver_id"],
            how="inner",
        )

    metrics = {
        "analytics_points_trend": compute_points_trend(race_results),
        "analytics_rolling_position": rolling_position,
        "analytics_recent_form": compute_recent_form(race_results),
        "analytics_teammate_comparison": compute_teammate_comparison(race_results),
    }

    counts = {}
    for table, df in metrics.items():
        counts[table] = db.replace_table(df, table)
        logger.info("Analytics table %s: %s rows", table, counts[table])

    return counts


def _empty_points_trend() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "season", "round", "driver_id", "race_points",
        "cumulative_points", "season_avg_points_per_race",
    ])


def _empty_rolling_position() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "season", "round", "driver_id", "rolling_avg_position", "races_in_window",
    ])


def _empty_recent_form() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "season", "round", "driver_id", "recent_form_points", "races_in_window",
    ])


def _empty_teammate_comparison() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "season", "round", "team_id", "driver_id", "teammate_driver_id",
        "driver_points", "teammate_points", "points_advantage", "position_advantage",
    ])

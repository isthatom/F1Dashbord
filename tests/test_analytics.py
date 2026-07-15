"""Unit tests for src/analytics.py using small hand-built DataFrames."""

import pytest
import pandas as pd

from src import analytics as an


def _sample_race_results() -> pd.DataFrame:
    """
    Two drivers (VER & PER) at red_bull, three races in 2024.

    VER: P1 (25pts), P2 (18pts), NC/DNF (0pts)  -> positions 1, 2, NaN
    PER: P3 (15pts), P4 (12pts), P5 (10pts)
    """
    return pd.DataFrame([
        {"season": 2024, "round": 1, "driver_id": "verstappen", "team_id": "red_bull",
         "position": 1, "finished": 1, "points": 25},
        {"season": 2024, "round": 1, "driver_id": "perez", "team_id": "red_bull",
         "position": 3, "finished": 1, "points": 15},
        {"season": 2024, "round": 2, "driver_id": "verstappen", "team_id": "red_bull",
         "position": 2, "finished": 1, "points": 18},
        {"season": 2024, "round": 2, "driver_id": "perez", "team_id": "red_bull",
         "position": 4, "finished": 1, "points": 12},
        {"season": 2024, "round": 3, "driver_id": "verstappen", "team_id": "red_bull",
         "position": None, "finished": 0, "points": 0},
        {"season": 2024, "round": 3, "driver_id": "perez", "team_id": "red_bull",
         "position": 5, "finished": 1, "points": 10},
    ])


def test_compute_points_trend_cumulative_and_average():
    df = an.compute_points_trend(_sample_race_results())
    ver = df[df["driver_id"] == "verstappen"].sort_values("round")

    assert ver.iloc[0]["race_points"] == 25
    assert ver.iloc[0]["cumulative_points"] == 25
    assert ver.iloc[0]["season_avg_points_per_race"] == 25

    assert ver.iloc[1]["cumulative_points"] == 43
    assert ver.iloc[1]["season_avg_points_per_race"] == 21.5

    assert ver.iloc[2]["cumulative_points"] == 43
    assert ver.iloc[2]["season_avg_points_per_race"] == pytest.approx(43 / 3)


def test_compute_rolling_position_excludes_dnf():
    df = an.compute_rolling_position(_sample_race_results(), window=5)
    ver = df[df["driver_id"] == "verstappen"].sort_values("round")

    # Round 1: only one finished race
    assert ver.iloc[0]["rolling_avg_position"] == 1.0
    assert ver.iloc[0]["races_in_window"] == 1

    # Round 2: avg of P1 and P2
    assert ver.iloc[1]["rolling_avg_position"] == 1.5
    assert ver.iloc[1]["races_in_window"] == 2

    # Round 3: DNF excluded — still avg of P1 and P2
    assert ver.iloc[2]["rolling_avg_position"] == 1.5
    assert ver.iloc[2]["races_in_window"] == 2


def test_compute_recent_form_sums_last_five():
    df = an.compute_recent_form(_sample_race_results(), window=5)
    ver = df[df["driver_id"] == "verstappen"].sort_values("round")

    assert ver.iloc[0]["recent_form_points"] == 25
    assert ver.iloc[1]["recent_form_points"] == 43
    # DNF counts as 0 points but is included in the window
    assert ver.iloc[2]["recent_form_points"] == 43
    assert ver.iloc[2]["races_in_window"] == 3


def test_compute_teammate_comparison_points_and_position():
    df = an.compute_teammate_comparison(_sample_race_results())
    r1_ver = df[
        (df["round"] == 1) & (df["driver_id"] == "verstappen")
    ].iloc[0]

    assert r1_ver["teammate_driver_id"] == "perez"
    assert r1_ver["points_advantage"] == 10  # 25 - 15
    assert r1_ver["position_advantage"] == 2  # teammate P3 - driver P1


def test_compute_teammate_comparison_skips_non_pair_teams():
    df = pd.DataFrame([
        {"season": 2024, "round": 1, "team_id": "solo", "driver_id": "alone",
         "position": 1, "points": 25},
    ])
    result = an.compute_teammate_comparison(df)
    assert result.empty


def test_empty_race_results_return_empty_frames():
    empty = pd.DataFrame()
    assert an.compute_points_trend(empty).empty
    assert an.compute_rolling_position(empty).empty
    assert an.compute_recent_form(empty).empty
    assert an.compute_teammate_comparison(empty).empty


def test_run_analytics_persists_to_db(test_db):
    results = _sample_race_results()
    test_db.upsert_race_results(results)

    counts = an.run_analytics(test_db)

    assert counts["analytics_points_trend"] == 6
    assert counts["analytics_teammate_comparison"] == 6
    assert counts["analytics_recent_form"] == 6
    # rolling position only includes finished races (5 of 6 rows)
    assert counts["analytics_rolling_position"] == 5

    stored = test_db.read_race_results()
    assert len(stored) == 6

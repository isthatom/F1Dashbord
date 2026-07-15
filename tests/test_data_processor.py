"""Unit tests for src/data_processor.py."""

import pandas as pd

from src import data_processor as dp


# ---------------------------------------------------------------------------
# Empty / missing responses
# ---------------------------------------------------------------------------

def test_drivers_to_df_empty_response():
    df = dp.drivers_to_df({})
    assert df.empty
    assert list(df.columns) == [
        "driver_id", "full_name", "nationality", "birthday", "number", "shortname", "team_id",
    ]


def test_teams_to_df_empty_response():
    df = dp.teams_to_df({"teams": []})
    assert df.empty


def test_races_to_df_empty_response():
    df = dp.races_to_df({})
    assert df.empty


def test_race_results_to_df_empty_results():
    df = dp.race_results_to_df({"races": {"results": []}}, season=2024, round_number=1)
    assert df.empty


def test_circuits_to_df_empty_response():
    df = dp.circuits_to_df({})
    assert df.empty


# ---------------------------------------------------------------------------
# Missing / null fields
# ---------------------------------------------------------------------------

def test_drivers_to_df_missing_fields():
    raw = {
        "drivers": [
            {"driverId": "test_driver"},  # only ID present
            {},  # completely empty driver object
        ]
    }
    df = dp.drivers_to_df(raw)
    assert len(df) == 2
    assert df.iloc[0]["driver_id"] == "test_driver"
    assert df.iloc[0]["full_name"] == ""
    assert pd.isna(df.iloc[0]["nationality"])
    assert df.iloc[1]["driver_id"] is None


def test_teams_to_df_missing_fields():
    raw = {"teams": [{"teamId": "ferrari"}]}
    df = dp.teams_to_df(raw)
    assert df.iloc[0]["team_id"] == "ferrari"
    assert df.iloc[0]["team_name"] is None


def test_races_to_df_missing_circuit_and_schedule():
    raw = {
        "season": 2024,
        "races": [{"round": 1, "raceName": "Test Grand Prix"}],
    }
    df = dp.races_to_df(raw)
    assert df.iloc[0]["season"] == 2024
    assert df.iloc[0]["race_name"] == "Test Grand Prix"
    assert df.iloc[0]["circuit_id"] is None
    assert df.iloc[0]["race_date"] is None


def test_driver_standings_to_df_uses_top_level_driver_id():
    raw = {
        "drivers_championship": [
            {
                "driverId": "verstappen",
                "position": 1,
                "points": 100,
                "wins": 5,
                "driver": {"name": "Max", "surname": "Verstappen"},
                "team": {"teamName": "Red Bull"},
            }
        ]
    }
    df = dp.driver_standings_to_df(raw, season=2024)
    assert df.iloc[0]["driver_id"] == "verstappen"
    assert df.iloc[0]["driver_name"] == "Max Verstappen"


# ---------------------------------------------------------------------------
# DNF / non-numeric position ("NC")
# ---------------------------------------------------------------------------

def test_race_results_to_df_nc_position():
    raw = {
        "races": {
            "raceName": "Monaco GP",
            "results": [
                {
                    "position": "NC",
                    "driver": {"driverId": "sainz", "name": "Carlos", "surname": "Sainz"},
                    "team": {"teamId": "ferrari", "teamName": "Ferrari"},
                    "points": 0,
                    "grid": 3,
                    "retired": "Accident",
                },
                {
                    "position": 1,
                    "driver": {"driverId": "norris", "name": "Lando", "surname": "Norris"},
                    "team": {"teamId": "mclaren", "teamName": "McLaren"},
                    "points": 25,
                    "grid": 1,
                },
            ],
        }
    }
    df = dp.race_results_to_df(raw, season=2024, round_number=8)
    nc = df[df["driver_id"] == "sainz"].iloc[0]
    winner = df[df["driver_id"] == "norris"].iloc[0]

    assert nc["finished"] == 0
    assert pd.isna(nc["position"])
    assert winner["finished"] == 1
    assert winner["position"] == 1


def test_race_results_to_df_null_position():
    raw = {
        "races": {
            "results": [
                {
                    "position": None,
                    "driver": {"driverId": "p1"},
                    "team": {"teamId": "t1"},
                }
            ]
        }
    }
    df = dp.race_results_to_df(raw, season=2024, round_number=1)
    assert df.iloc[0]["finished"] == 0
    assert pd.isna(df.iloc[0]["position"])


# ---------------------------------------------------------------------------
# API response shape quirks
# ---------------------------------------------------------------------------

def test_races_to_df_current_season_uses_race_key():
    raw = {
        "season": 2026,
        "race": [{"round": 1, "raceName": "Australian GP", "circuit": {"circuitId": "albert_park"}}],
    }
    df = dp.races_to_df(raw)
    assert len(df) == 1
    assert df.iloc[0]["circuit_id"] == "albert_park"


def test_circuits_from_races_df_deduplicates():
    races = pd.DataFrame([
        {"circuit_id": "monaco", "circuit_name": "Monaco", "city": "Monte Carlo", "country": "Monaco"},
        {"circuit_id": "monaco", "circuit_name": "Monaco", "city": "Monte Carlo", "country": "Monaco"},
        {"circuit_id": None, "circuit_name": None, "city": None, "country": None},
    ])
    circuits = dp.circuits_from_races_df(races)
    assert len(circuits) == 1

"""Integration-style tests for src/fetch_data.py error handling."""

from unittest.mock import MagicMock, patch

from src.api_client import F1ApiError, F1ApiNotFoundError
from src.fetch_data import run


def _drivers_payload():
    return {
        "drivers": [
            {
                "driverId": "verstappen",
                "name": "Max",
                "surname": "Verstappen",
                "nationality": "Dutch",
                "teamId": "red_bull",
            }
        ]
    }


def _teams_payload():
    return {"teams": [{"teamId": "red_bull", "teamName": "Red Bull"}]}


def _races_payload():
    return {
        "season": 2024,
        "races": [
            {
                "round": 1,
                "raceName": "Test GP",
                "circuit": {"circuitId": "test_circuit", "circuitName": "Test Circuit"},
            }
        ],
    }


def _standings_payload():
    return {
        "drivers_championship": [
            {
                "driverId": "verstappen",
                "position": 1,
                "points": 25,
                "wins": 1,
                "driver": {"name": "Max", "surname": "Verstappen"},
                "team": {"teamName": "Red Bull"},
            }
        ]
    }


def _constructor_standings_payload():
    return {
        "constructors_championship": [
            {
                "teamId": "red_bull",
                "position": 1,
                "points": 25,
                "wins": 1,
                "team": {"teamName": "Red Bull"},
            }
        ]
    }


def _race_result_payload():
    return {
        "races": {
            "raceName": "Test GP",
            "results": [
                {
                    "position": 1,
                    "driver": {"driverId": "verstappen", "name": "Max", "surname": "Verstappen"},
                    "team": {"teamId": "red_bull", "teamName": "Red Bull"},
                    "points": 25,
                    "grid": 1,
                }
            ],
        }
    }


def _configure_mock_client(mock_cls):
    """Return a mock client where circuits fails but season data succeeds."""
    client = MagicMock()
    mock_cls.return_value = client

    client.get_circuits.side_effect = F1ApiError("Connection timed out")
    client.get_drivers.return_value = _drivers_payload()
    client.get_teams.return_value = _teams_payload()
    client.get_races.return_value = _races_payload()
    client.get_driver_standings.return_value = _standings_payload()
    client.get_constructor_standings.return_value = _constructor_standings_payload()
    client.get_race_results.return_value = _race_result_payload()
    client.get_latest_race_results.return_value = {
        "season": 2024,
        "races": {"round": 1},
    }
    return client


@patch("src.fetch_data.SAVE_RAW_JSON", False)
@patch("src.fetch_data.F1ApiClient")
def test_pipeline_continues_when_circuits_endpoint_fails(mock_client_cls, test_db_path):
    _configure_mock_client(mock_client_cls)

    summary = run(
        season="2024",
        fetch_race_results=True,
        db_path=test_db_path,
        write_summary=False,
    )

    assert summary.error_count == 1
    assert summary.errors[0]["endpoint"] == "circuits"
    assert summary.errors[0]["error_type"] == "F1ApiError"
    assert summary.tables.get("drivers", 0) > 0
    assert summary.tables.get("race_results", 0) > 0


@patch("src.fetch_data.SAVE_RAW_JSON", False)
@patch("src.fetch_data.F1ApiClient")
def test_pipeline_continues_when_race_result_returns_404(mock_client_cls, test_db_path):
    client = _configure_mock_client(mock_client_cls)
    client.get_race_results.side_effect = F1ApiNotFoundError("Resource not available")

    summary = run(
        season="2024",
        fetch_race_results=True,
        db_path=test_db_path,
        write_summary=False,
    )

    assert any(e["error_type"] == "F1ApiNotFoundError" for e in summary.errors)
    assert summary.tables.get("drivers", 0) > 0
    # race_results should not have been loaded
    assert summary.tables.get("race_results", 0) in (0, None)


@patch("src.fetch_data.SAVE_RAW_JSON", False)
@patch("src.fetch_data.F1ApiClient")
def test_pipeline_continues_when_drivers_endpoint_fails(mock_client_cls, test_db_path):
    client = _configure_mock_client(mock_client_cls)
    client.get_circuits.return_value = {"circuits": []}
    client.get_drivers.side_effect = F1ApiError("HTTP 500")

    summary = run(
        season="2024",
        fetch_race_results=False,
        db_path=test_db_path,
        write_summary=False,
    )

    assert summary.error_count >= 1
    assert any(e["endpoint"] == "2024/drivers" for e in summary.errors)
    assert summary.tables.get("teams", 0) > 0


@patch("src.fetch_data.SAVE_RAW_JSON", False)
@patch("src.fetch_data.F1ApiClient")
def test_run_summary_written_to_file(mock_client_cls, test_db_path, tmp_path):
    _configure_mock_client(mock_client_cls)
    summary_path = tmp_path / "run_summary.json"


    summary = run(
        season="2024",
        fetch_race_results=False,
        db_path=test_db_path,
        write_summary=False,
    )
    summary.write(summary_path)

    assert summary_path.exists()
    payload = summary_path.read_text(encoding="utf-8")
    assert "duration_seconds" in payload
    assert "tables" in payload
    assert "seasons" in payload

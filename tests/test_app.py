"""Smoke tests for the Streamlit preview app (app.py)."""

import sqlite3
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import config.settings as settings
from app import (
    load_constructor_standings,
    load_driver_standings,
    load_h2h_summary,
    load_podium_counts,
    load_points_trend,
    load_position_matrix,
    load_race_results,
    load_recent_form,
    load_rolling_position,
    load_rounds,
    load_seasons,
    load_teammate_h2h,
)

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

TAB_LABELS = ["Season Hub", "Points Trend", "Race Positions", "Teammate H2H", "Race Results"]

TEAM_OF = {"ham": "mercedes", "rus": "mercedes", "lec": "ferrari", "sai": "ferrari"}
TEAM_NAMES = {"mercedes": "Mercedes Formula 1 Team", "ferrari": "Scuderia Ferrari"}
TEAMMATE = {"ham": "rus", "rus": "ham", "lec": "sai", "sai": "lec"}
DRIVERS = ["ham", "rus", "lec", "sai"]

# (round, driver, position, grid, points)
RESULTS = [
    (1, "ham", 1.0, 1, 25.0),
    (1, "rus", 2.0, 2, 18.0),
    (1, "lec", 3.0, 3, 15.0),
    (1, "sai", 4.0, 4, 12.0),
    (2, "lec", 1.0, 2, 25.0),
    (2, "ham", 2.0, 1, 18.0),
    (2, "sai", 3.0, 3, 15.0),
    (2, "rus", 4.0, 4, 12.0),
]


def _create_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE teams (
            team_id TEXT PRIMARY KEY, team_name TEXT, nationality TEXT,
            first_appearance INTEGER, constructors_championships INTEGER,
            drivers_championships INTEGER
        );
        CREATE TABLE drivers (
            driver_id TEXT PRIMARY KEY, full_name TEXT, nationality TEXT,
            birthday TEXT, number INTEGER, shortname TEXT
        );
        CREATE TABLE races (
            season INTEGER NOT NULL, round INTEGER NOT NULL, race_id TEXT,
            race_name TEXT, race_date TEXT, circuit_id TEXT,
            PRIMARY KEY (season, round)
        );
        CREATE TABLE race_results (
            season INTEGER NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
            team_id TEXT, position REAL, finished INTEGER, grid INTEGER,
            points REAL, time TEXT, retired TEXT,
            PRIMARY KEY (season, round, driver_id)
        );
        CREATE TABLE driver_standings (
            season INTEGER NOT NULL, driver_id TEXT NOT NULL, position INTEGER,
            team_name TEXT, points REAL, wins INTEGER, team_id TEXT,
            PRIMARY KEY (season, driver_id)
        );
        CREATE TABLE constructor_standings (
            season INTEGER NOT NULL, team_id TEXT NOT NULL, position INTEGER,
            team_name TEXT, points REAL, wins INTEGER,
            PRIMARY KEY (season, team_id)
        );
        CREATE TABLE analytics_points_trend (
            season INTEGER NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
            race_points REAL, cumulative_points REAL, season_avg_points_per_race REAL,
            PRIMARY KEY (season, round, driver_id)
        );
        CREATE TABLE analytics_rolling_position (
            season INTEGER NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
            rolling_avg_position REAL, races_in_window INTEGER,
            PRIMARY KEY (season, round, driver_id)
        );
        CREATE TABLE analytics_recent_form (
            season INTEGER NOT NULL, round INTEGER NOT NULL, driver_id TEXT NOT NULL,
            recent_form_points REAL, races_in_window INTEGER,
            PRIMARY KEY (season, round, driver_id)
        );
        CREATE TABLE analytics_teammate_comparison (
            season INTEGER NOT NULL, round INTEGER NOT NULL, team_id TEXT NOT NULL,
            driver_id TEXT NOT NULL, teammate_driver_id TEXT NOT NULL,
            driver_points REAL, teammate_points REAL,
            points_advantage REAL, position_advantage REAL,
            PRIMARY KEY (season, round, driver_id)
        );
        CREATE TABLE pipeline_meta (
            key TEXT PRIMARY KEY, value TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    cur.executemany(
        "INSERT INTO teams VALUES (?,?,?,?,?,?)",
        [
            ("mercedes", TEAM_NAMES["mercedes"], "German", 1954, 8, 9),
            ("ferrari", TEAM_NAMES["ferrari"], "Italian", 1950, 16, 16),
        ],
    )
    cur.executemany(
        "INSERT INTO drivers VALUES (?,?,?,?,?,?)",
        [
            ("ham", "Lewis Hamilton", "British", "1985-01-07", 44, "HAM"),
            ("rus", "George Russell", "British", "1998-02-15", 63, "RUS"),
            ("lec", "Charles Leclerc", "Monegasque", "1997-10-16", 16, "LEC"),
            ("sai", "Carlos Sainz", "Spanish", "1994-09-01", 55, "SAI"),
        ],
    )
    for rnd in (1, 2):
        cur.execute(
            "INSERT INTO races VALUES (?,?,?,?,?,?)",
            (2026, rnd, f"r{rnd}", f"Round {rnd}", f"2026-03-0{rnd}", "c1"),
        )
    cur.executemany(
        "INSERT INTO race_results VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                2026,
                rnd,
                d,
                TEAM_OF[d],
                pos,
                1,
                grid,
                pts,
                "x",
                None,
            )
            for rnd, d, pos, grid, pts in RESULTS
        ],
    )
    cur.execute(
        "UPDATE race_results SET grid='not available' "
        "WHERE season=2026 AND round=2 AND driver_id='sai'"
    )

    standings = []
    for i, (d, pts) in enumerate(
        [
            ("ham", 43.0),
            ("lec", 40.0),
            ("rus", 30.0),
            ("sai", 27.0),
        ],
        start=1,
    ):
        standings.append((2026, d, i, TEAM_NAMES[TEAM_OF[d]], pts, 0, TEAM_OF[d]))
    cur.executemany("INSERT INTO driver_standings VALUES (?,?,?,?,?,?,?)", standings)
    cur.executemany(
        "INSERT INTO constructor_standings VALUES (?,?,?,?,?,?)",
        [
            (2026, "mercedes", 1, TEAM_NAMES["mercedes"], 73.0, 0),
            (2026, "ferrari", 2, TEAM_NAMES["ferrari"], 67.0, 1),
        ],
    )

    points = {(rnd, d): pts for rnd, d, _pos, _grid, pts in RESULTS}
    positions = {(rnd, d): pos for rnd, d, pos, _grid, _pts in RESULTS}
    trend, roll, form, h2h = [], [], [], []
    for rnd in (1, 2):
        for d in DRIVERS:
            race_pts = points[(rnd, d)]
            cum = sum(points[(r, d)] for r in range(1, rnd + 1))
            pos_window = [positions[(r, d)] for r in range(1, rnd + 1)]
            start = max(1, rnd - 2)
            form_pts = sum(points[(r, d)] for r in range(start, rnd + 1)) / (rnd - start + 1)
            trend.append((2026, rnd, d, race_pts, cum, cum / rnd))
            roll.append((2026, rnd, d, sum(pos_window) / len(pos_window), rnd))
            form.append((2026, rnd, d, form_pts, rnd))
            mate = TEAMMATE[d]
            adv = race_pts - points[(rnd, mate)]
            pos_adv = positions[(rnd, mate)] - positions[(rnd, d)]
            h2h.append(
                (
                    2026,
                    rnd,
                    TEAM_OF[d],
                    d,
                    mate,
                    race_pts,
                    points[(rnd, mate)],
                    adv,
                    pos_adv,
                )
            )
    cur.executemany("INSERT INTO analytics_points_trend VALUES (?,?,?,?,?,?)", trend)
    cur.executemany("INSERT INTO analytics_rolling_position VALUES (?,?,?,?,?)", roll)
    cur.executemany("INSERT INTO analytics_recent_form VALUES (?,?,?,?,?)", form)
    cur.executemany("INSERT INTO analytics_teammate_comparison VALUES (?,?,?,?,?,?,?,?,?)", h2h)
    cur.execute(
        "INSERT INTO pipeline_meta VALUES (?,?,datetime('now'))",
        ("finished_at", '"2026-08-01T12:00:00"'),
    )
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def clear_app_cache():
    st.cache_data.clear()
    yield


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    db = tmp_path / "f1.db"
    _create_db(db)
    monkeypatch.setattr(settings, "DB_PATH", str(db))
    return db


def test_app_renders_all_tabs(app_db):
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    assert not at.exception
    assert [t.label for t in at.tabs] == TAB_LABELS
    assert any("Last pipeline run" in c.value for c in at.caption)
    assert any(m.label == "Championship leader" for m in at.metric)
    assert at.sidebar.selectbox[0].options == ["2026"]
    assert set(at.sidebar.multiselect[0].options) == {
        "Lewis Hamilton",
        "George Russell",
        "Charles Leclerc",
        "Carlos Sainz",
    }


def test_app_switches_season(app_db):
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    seasons = list(at.sidebar.selectbox[0].options)
    if seasons:
        at.sidebar.selectbox[0].select(seasons[-1]).run()
        assert not at.exception


def test_app_widgets_interact(app_db):
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    radio = next(w for w in at.radio if w.label == "Measure")
    radio.set_value("Avg points per race").run()
    assert not at.exception

    team_sel = next(w for w in at.selectbox if w.key == "h2h_team")
    team_sel.select(team_sel.options[0]).run()
    assert not at.exception

    round_sel = next(w for w in at.selectbox if w.key == "race_round")
    round_sel.select(round_sel.options[-1]).run()
    assert not at.exception


def test_app_empty_db_shows_info(tmp_path, monkeypatch):
    db = tmp_path / "empty.db"
    sqlite3.connect(db).close()
    monkeypatch.setattr(settings, "DB_PATH", str(db))

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()

    assert not at.exception
    assert any("No races" in str(i.value) for i in at.info)
    assert not at.tabs


def test_loaders_return_expected_columns(app_db):
    assert load_seasons() == [2026]
    ds = load_driver_standings(2026)
    assert list(ds.columns) == ["position", "driver_id", "full_name", "team_name", "points", "wins"]
    assert len(ds) == 4
    cs = load_constructor_standings(2026)
    assert len(cs) == 2
    pods = load_podium_counts(2026)
    assert pods["wins"].iloc[0] == 1
    trend = load_points_trend(2026, ("ham", "lec"))
    assert set(trend["full_name"]) == {"Lewis Hamilton", "Charles Leclerc"}
    assert set(trend.columns) >= {"race_points", "cumulative_points", "season_avg_points_per_race"}
    mat = load_position_matrix(2026, tuple(DRIVERS))
    assert len(mat) == 8
    roll = load_rolling_position(2026, ("ham",))
    assert "rolling_avg_position" in roll.columns
    form = load_recent_form(2026, ("ham",))
    assert "recent_form_points" in form.columns
    h2h = load_teammate_h2h(2026)
    assert len(h2h) == 8
    summary = load_h2h_summary(2026)
    assert len(summary) == 4
    assert "h2h_wins" in summary.columns
    rounds = load_rounds(2026)
    assert list(rounds["round"]) == [1, 2]
    rr = load_race_results(2026, 1)
    assert list(rr["position"]) == [1.0, 2.0, 3.0, 4.0]

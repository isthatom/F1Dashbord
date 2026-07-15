"""
SQLite storage for the F1 data pipeline.

Star schema (Power BI friendly):
    Dimensions : drivers, teams, circuits, races
    Fact       : race_results

Additional tables (not part of the core star schema, but useful in Power BI):
    driver_standings, constructor_standings

Every table uses explicit primary keys and foreign keys so Power BI's
SQLite connector can auto-detect relationships.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from config.settings import DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS circuits (
    circuit_id          TEXT PRIMARY KEY,
    circuit_name        TEXT,
    city                TEXT,
    country             TEXT
);

CREATE TABLE IF NOT EXISTS teams (
    team_id                     TEXT PRIMARY KEY,
    team_name                   TEXT,
    nationality                 TEXT,
    first_appearance            TEXT,
    constructors_championships  REAL,
    drivers_championships       REAL
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id     TEXT PRIMARY KEY,
    full_name     TEXT,
    nationality   TEXT,
    birthday      TEXT,
    number        INTEGER,
    shortname     TEXT
);

CREATE TABLE IF NOT EXISTS races (
    season        INTEGER NOT NULL,
    round         INTEGER NOT NULL,
    race_id       TEXT,
    race_name     TEXT,
    race_date     TEXT,
    circuit_id    TEXT,
    PRIMARY KEY (season, round),
    FOREIGN KEY (circuit_id) REFERENCES circuits(circuit_id)
);

CREATE TABLE IF NOT EXISTS race_results (
    season        INTEGER NOT NULL,
    round         INTEGER NOT NULL,
    driver_id     TEXT NOT NULL,
    team_id       TEXT,
    position      INTEGER,
    finished      INTEGER,
    grid          INTEGER,
    points        REAL,
    time          TEXT,
    retired       TEXT,
    PRIMARY KEY (season, round, driver_id),
    FOREIGN KEY (season, round) REFERENCES races(season, round),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS driver_standings (
    season        INTEGER NOT NULL,
    driver_id     TEXT NOT NULL,
    position      INTEGER,
    team_name     TEXT,
    points        REAL,
    wins          INTEGER,
    PRIMARY KEY (season, driver_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS constructor_standings (
    season        INTEGER NOT NULL,
    team_id       TEXT NOT NULL,
    position      INTEGER,
    team_name     TEXT,
    points        REAL,
    wins          INTEGER,
    PRIMARY KEY (season, team_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE TABLE IF NOT EXISTS analytics_points_trend (
    season                      INTEGER NOT NULL,
    round                       INTEGER NOT NULL,
    driver_id                   TEXT NOT NULL,
    race_points                 REAL,
    cumulative_points           REAL,
    season_avg_points_per_race  REAL,
    PRIMARY KEY (season, round, driver_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS analytics_rolling_position (
    season                  INTEGER NOT NULL,
    round                   INTEGER NOT NULL,
    driver_id               TEXT NOT NULL,
    rolling_avg_position    REAL,
    races_in_window         INTEGER,
    PRIMARY KEY (season, round, driver_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS analytics_recent_form (
    season              INTEGER NOT NULL,
    round               INTEGER NOT NULL,
    driver_id           TEXT NOT NULL,
    recent_form_points  REAL,
    races_in_window     INTEGER,
    PRIMARY KEY (season, round, driver_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)
);

CREATE TABLE IF NOT EXISTS analytics_teammate_comparison (
    season                INTEGER NOT NULL,
    round                 INTEGER NOT NULL,
    team_id               TEXT NOT NULL,
    driver_id             TEXT NOT NULL,
    teammate_driver_id    TEXT NOT NULL,
    driver_points         REAL,
    teammate_points       REAL,
    points_advantage      REAL,
    position_advantage    REAL,
    PRIMARY KEY (season, round, driver_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
"""


class F1Database:
    """Thin wrapper around the SQLite database file."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info("Database ready at %s", self.db_path)

    # -----------------------------------------------------------------
    # Incremental-load helpers
    # -----------------------------------------------------------------
    def race_results_exist(self, season: int, round_number: int) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM race_results WHERE season = ? AND round = ? LIMIT 1",
                (season, round_number),
            ).fetchone()
        return row is not None

    def count_race_result_rounds(self, season: int) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT round) FROM race_results WHERE season = ?",
                (season,),
            ).fetchone()
        return row[0] if row else 0

    def read_race_results(self) -> pd.DataFrame:
        """Load the full race_results fact table for analytics."""
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM race_results ORDER BY season, round", conn)

    def replace_table(self, df: pd.DataFrame, table: str) -> int:
        """Replace an entire table (used for analytics tables that are fully recomputed)."""
        with self.connect() as conn:
            conn.execute(f"DELETE FROM {table}")
            if df.empty:
                return 0
            df.to_sql(table, conn, if_exists="append", index=False)
        count = len(df)
        logger.info("Replaced %s with %s rows", table, count)
        return count

    # -----------------------------------------------------------------
    # Upsert helpers — one per table
    # -----------------------------------------------------------------
    def upsert_circuits(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        return self._upsert(
            df[["circuit_id", "circuit_name", "city", "country"]].drop_duplicates("circuit_id"),
            "circuits",
            "circuit_id",
        )

    def upsert_teams(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = [
            "team_id", "team_name", "nationality", "first_appearance",
            "constructors_championships", "drivers_championships",
        ]
        return self._upsert(df[cols].drop_duplicates("team_id"), "teams", "team_id")

    def upsert_drivers(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = ["driver_id", "full_name", "nationality", "birthday", "number", "shortname"]
        return self._upsert(df[cols].drop_duplicates("driver_id"), "drivers", "driver_id")

    def upsert_races(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = ["season", "round", "race_id", "race_name", "race_date", "circuit_id"]
        return self._upsert(df[cols], "races", ["season", "round"])

    def upsert_race_results(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = [
            "season", "round", "driver_id", "team_id", "position", "finished",
            "grid", "points", "time", "retired",
        ]
        df = df.copy()
        for col in cols:
            if col not in df.columns:
                df[col] = None
        self._insert_missing_race_result_dependencies(df)
        return self._upsert(df[cols], "race_results", ["season", "round", "driver_id"])

    def _insert_missing_race_result_dependencies(self, df: pd.DataFrame) -> None:
        """Insert placeholder dimension rows needed by race_results foreign keys."""
        with self.connect() as conn:
            for driver_id in df["driver_id"].dropna().drop_duplicates():
                conn.execute(
                    "INSERT OR IGNORE INTO drivers (driver_id) VALUES (?)",
                    (driver_id,),
                )
            for team_id in df["team_id"].dropna().drop_duplicates():
                conn.execute(
                    "INSERT OR IGNORE INTO teams (team_id) VALUES (?)",
                    (team_id,),
                )
            races = df[["season", "round"]].dropna().drop_duplicates()
            for row in races.itertuples(index=False):
                conn.execute(
                    "INSERT OR IGNORE INTO races (season, round) VALUES (?, ?)",
                    (int(row.season), int(row.round)),
                )

    def upsert_driver_standings(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = ["season", "driver_id", "position", "team_name", "points", "wins"]
        clean = df[cols].dropna(subset=["driver_id"])
        return self._upsert(clean, "driver_standings", ["season", "driver_id"])

    def upsert_constructor_standings(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        cols = ["season", "team_id", "position", "team_name", "points", "wins"]
        clean = df[cols].dropna(subset=["team_id"])
        return self._upsert(clean, "constructor_standings", ["season", "team_id"])

    def _upsert(self, df: pd.DataFrame, table: str, conflict_cols: str | list[str]) -> int:
        if df.empty:
            return 0

        if isinstance(conflict_cols, str):
            conflict_cols = [conflict_cols]

        columns = list(df.columns)
        placeholders = ", ".join("?" for _ in columns)
        col_list = ", ".join(columns)
        update_cols = [c for c in columns if c not in conflict_cols]
        conflict_clause = ", ".join(conflict_cols)

        if update_cols:
            set_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT({conflict_clause}) DO UPDATE SET {set_clause}"
            )
        else:
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                f"ON CONFLICT({conflict_clause}) DO NOTHING"
            )

        rows = [tuple(None if pd.isna(v) else v for v in row) for row in df.itertuples(index=False)]

        with self.connect() as conn:
            conn.executemany(sql, rows)

        logger.info("Upserted %s rows into %s", len(rows), table)
        return len(rows)

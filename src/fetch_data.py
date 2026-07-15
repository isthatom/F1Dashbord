"""
Orchestrates the full pipeline:

    F1 API  --(api_client)-->  raw JSON  --(data_processor)-->  SQLite DB
                                                          -->  analytics tables
                                                          -->  run_summary.json

Raw JSON is saved to data/raw/ purely as a debugging aid. The SQLite
database at data/f1.db is what Power BI connects to.
"""

import json
import logging

import pandas as pd

from config.settings import (
    EXPORT_CSV,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    SAVE_RAW_JSON,
    resolve_season_list,
)
from src.analytics import run_analytics
from src.api_client import F1ApiClient, F1ApiError, F1ApiNotFoundError
from src.database import F1Database
from src.run_summary import RunSummary
from src import data_processor as dp

logger = logging.getLogger(__name__)


def _save_raw_json(name: str, payload: dict) -> None:
    path = RAW_DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Saved raw JSON -> %s", path)


def _save_csv(df: pd.DataFrame, name: str) -> None:
    path = PROCESSED_DATA_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    logger.info("Saved CSV (%s rows) -> %s", len(df), path)


def _record_upsert(summary: RunSummary | None, table: str, rows: int) -> None:
    if summary is not None:
        summary.record_table(table, rows)


def _upsert_drivers_from_standings(db: F1Database, standings_df: pd.DataFrame) -> int:
    """Create minimal driver rows so standings can load after a drivers API failure."""
    if standings_df.empty or "driver_id" not in standings_df.columns:
        return 0

    drivers_df = pd.DataFrame({
        "driver_id": standings_df["driver_id"],
        "full_name": standings_df.get("driver_name"),
        "nationality": None,
        "birthday": None,
        "number": None,
        "shortname": None,
    }).dropna(subset=["driver_id"])
    return db.upsert_drivers(drivers_df)


def _fetch_global_circuits(
    client: F1ApiClient,
    db: F1Database,
    summary: RunSummary | None,
) -> None:
    endpoint = "circuits"
    try:
        raw_circuits = client.get_circuits()
        if SAVE_RAW_JSON:
            _save_raw_json("circuits", raw_circuits)
        rows = db.upsert_circuits(dp.circuits_to_df(raw_circuits))
        _record_upsert(summary, "circuits", rows)
    except F1ApiError as exc:
        logger.error("Skipping global circuits: %s", exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, error_type=type(exc).__name__)


def _fetch_season(
    season: str,
    *,
    client: F1ApiClient,
    db: F1Database,
    fetch_race_results: bool,
    export_csv: bool,
    summary: RunSummary | None,
) -> None:
    """Fetch and store all data for a single season token (year or 'current')."""
    season_client = F1ApiClient(season=season)
    resolved_season = season
    is_current = season == "current"

    # --- Drivers ---------------------------------------------------------
    endpoint = f"{season}/drivers"
    try:
        raw_drivers = season_client.get_drivers()
        if SAVE_RAW_JSON:
            _save_raw_json(f"{season}_drivers", raw_drivers)
        drivers_df = dp.drivers_to_df(raw_drivers)
        rows = db.upsert_drivers(drivers_df)
        _record_upsert(summary, "drivers", rows)
        if export_csv:
            _save_csv(drivers_df, "drivers")
    except F1ApiError as exc:
        logger.error("Skipping drivers for %s: %s", season, exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, season=season, error_type=type(exc).__name__)

    # --- Teams -----------------------------------------------------------
    endpoint = f"{season}/teams"
    try:
        raw_teams = season_client.get_teams()
        if SAVE_RAW_JSON:
            _save_raw_json(f"{season}_teams", raw_teams)
        teams_df = dp.teams_to_df(raw_teams)
        rows = db.upsert_teams(teams_df)
        _record_upsert(summary, "teams", rows)
        if export_csv:
            _save_csv(teams_df, "teams")
    except F1ApiError as exc:
        logger.error("Skipping teams for %s: %s", season, exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, season=season, error_type=type(exc).__name__)

    # --- Races (calendar) ------------------------------------------------
    endpoint = season
    races_df = None
    try:
        raw_races = season_client.get_races()
        if SAVE_RAW_JSON:
            _save_raw_json(f"{season}_races", raw_races)
        if raw_races.get("season"):
            resolved_season = str(raw_races["season"])
        races_df = dp.races_to_df(raw_races, season=resolved_season)
        rows = db.upsert_circuits(dp.circuits_from_races_df(races_df))
        _record_upsert(summary, "circuits", rows)
        rows = db.upsert_races(races_df)
        _record_upsert(summary, "races", rows)
        if export_csv:
            _save_csv(races_df, "races")
    except F1ApiError as exc:
        logger.error("Skipping races for %s: %s", season, exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, season=season, error_type=type(exc).__name__)

    # --- Driver standings ------------------------------------------------
    endpoint = f"{season}/drivers-championship"
    try:
        raw_driver_standings = season_client.get_driver_standings()
        if SAVE_RAW_JSON:
            _save_raw_json(f"{season}_driver_standings", raw_driver_standings)
        driver_standings_df = dp.driver_standings_to_df(raw_driver_standings, resolved_season)
        _upsert_drivers_from_standings(db, driver_standings_df)
        rows = db.upsert_driver_standings(driver_standings_df)
        _record_upsert(summary, "driver_standings", rows)
        if export_csv:
            _save_csv(driver_standings_df, "driver_standings")
    except F1ApiError as exc:
        logger.error("Skipping driver standings for %s: %s", season, exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, season=season, error_type=type(exc).__name__)

    # --- Constructor standings -------------------------------------------
    endpoint = f"{season}/constructors-championship"
    try:
        raw_constructor_standings = season_client.get_constructor_standings()
        if SAVE_RAW_JSON:
            _save_raw_json(f"{season}_constructor_standings", raw_constructor_standings)
        constructor_standings_df = dp.constructor_standings_to_df(
            raw_constructor_standings, resolved_season
        )
        rows = db.upsert_constructor_standings(constructor_standings_df)
        _record_upsert(summary, "constructor_standings", rows)
        if export_csv:
            _save_csv(constructor_standings_df, "constructor_standings")
    except F1ApiError as exc:
        logger.error("Skipping constructor standings for %s: %s", season, exc)
        if summary:
            summary.record_error(str(exc), endpoint=endpoint, season=season, error_type=type(exc).__name__)

    # --- Race-by-race results (incremental) ------------------------------
    if fetch_race_results and races_df is not None and not races_df.empty:
        _fetch_race_results_incremental(
            season_token=season,
            resolved_season=int(resolved_season),
            races_df=races_df,
            client=client,
            db=db,
            is_current=is_current,
            export_csv=export_csv,
            summary=summary,
        )

    logger.info("Finished season=%s (resolved=%s)", season, resolved_season)


def _fetch_race_results_incremental(
    *,
    season_token: str,
    resolved_season: int,
    races_df: pd.DataFrame,
    client: F1ApiClient,
    db: F1Database,
    is_current: bool,
    export_csv: bool,
    summary: RunSummary | None,
) -> None:
    """
    Fetch per-round race results, skipping rounds already stored in the DB.

    For the current season, also caps fetches at the latest completed round
    reported by the API so we don't hammer 404s for future races.
    """
    last_completed_round = None
    if is_current:
        try:
            latest_result = client.get_latest_race_results()
            if int(latest_result.get("season", 0)) == resolved_season:
                latest_race = latest_result.get("races", {}) or {}
                last_completed_round = int(latest_race.get("round"))
        except (F1ApiError, TypeError, ValueError) as exc:
            logger.warning("Could not determine the latest completed race: %s", exc)
            if summary and isinstance(exc, F1ApiError):
                summary.record_error(
                    str(exc),
                    endpoint="current/last/race",
                    season=season_token,
                    error_type=type(exc).__name__,
                )

    rounds = races_df["round"].dropna().astype(int).tolist()
    if last_completed_round is not None:
        rounds = [r for r in rounds if r <= last_completed_round]

    season_results = []
    for round_number in rounds:
        endpoint = f"{resolved_season}/{round_number}/race"
        if db.race_results_exist(resolved_season, round_number):
            logger.info(
                "Skipping round %s (%s) — already in database.",
                round_number,
                resolved_season,
            )
            continue

        try:
            raw_result = client.get_race_results(round_number, season=str(resolved_season))
            result_df = dp.race_results_to_df(raw_result, resolved_season, round_number)
            rows = db.upsert_race_results(result_df)
            _record_upsert(summary, "race_results", rows)
            season_results.append(result_df)
            if SAVE_RAW_JSON:
                _save_raw_json(f"{season_token}_round_{round_number}_results", raw_result)
        except F1ApiNotFoundError as exc:
            logger.info("No results available yet for %s round %s; skipping.", resolved_season, round_number)
            if summary:
                summary.record_error(
                    str(exc),
                    endpoint=endpoint,
                    season=str(resolved_season),
                    round_number=round_number,
                    error_type="F1ApiNotFoundError",
                )
        except F1ApiError as exc:
            logger.error("Skipping results for %s round %s: %s", resolved_season, round_number, exc)
            if summary:
                summary.record_error(
                    str(exc),
                    endpoint=endpoint,
                    season=str(resolved_season),
                    round_number=round_number,
                    error_type=type(exc).__name__,
                )

    if export_csv and season_results:
        combined = pd.concat(season_results, ignore_index=True)
        _save_csv(combined, f"race_results_{resolved_season}")


def run(
    *,
    season: str | None = None,
    start_year: int | None = None,
    end_year: str | int | None = None,
    fetch_race_results: bool = True,
    export_csv: bool = False,
    db_path=None,
    write_summary: bool = True,
) -> RunSummary:
    """
    Pull F1 data for one or more seasons and write to SQLite.

    Returns the RunSummary object (also written to logs/run_summary.json).
    """
    seasons = resolve_season_list(season=season, start_year=start_year, end_year=end_year)
    summary = RunSummary()
    summary.set_seasons(seasons)

    db = F1Database(db_path) if db_path is not None else F1Database()
    db.initialize()

    client = F1ApiClient()
    _fetch_global_circuits(client, db, summary)

    for season_token in seasons:
        logger.info("=== Processing season: %s ===", season_token)
        _fetch_season(
            season_token,
            client=client,
            db=db,
            fetch_race_results=fetch_race_results,
            export_csv=export_csv,
            summary=summary,
        )

    if fetch_race_results:
        try:
            analytics_counts = run_analytics(db)
            for table, rows in analytics_counts.items():
                summary.record_table(table, rows)
        except Exception as exc:
            logger.error("Analytics computation failed: %s", exc)
            summary.record_error(
                str(exc),
                endpoint="analytics",
                error_type=type(exc).__name__,
            )

    logger.info("Pipeline finished for seasons: %s", ", ".join(seasons))

    if write_summary:
        summary.write()

    return summary

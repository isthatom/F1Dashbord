"""
Orchestrates the full pipeline:

    F1 API  --(api_client)-->  raw JSON  --(data_processor)-->  clean CSV

Raw JSON is saved to data/raw/ purely as a debugging aid (so you can see
exactly what the API sent back). The CSVs in data/processed/ are what
Power BI actually connects to.
"""

import json
import logging

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR
from src.api_client import F1ApiClient, F1ApiError
from src import data_processor as dp

logger = logging.getLogger(__name__)


def _save_raw_json(name: str, payload: dict) -> None:
    path = RAW_DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("Saved raw JSON -> %s", path)


def _save_csv(df, name: str) -> None:
    path = PROCESSED_DATA_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    logger.info("Saved CSV (%s rows) -> %s", len(df), path)


def run(season: str = "current", fetch_race_results: bool = True) -> None:
    """
    Pull everything needed for the Power BI dashboard for a given season:
    drivers, teams, races, driver standings, constructor standings, and
    (optionally) per-race results.
    """
    client = F1ApiClient(season=season)

    # --- Drivers -----------------------------------------------------
    try:
        raw_drivers = client.get_drivers()
        _save_raw_json(f"{season}_drivers", raw_drivers)
        _save_csv(dp.drivers_to_df(raw_drivers), "drivers")
    except F1ApiError as exc:
        logger.error("Skipping drivers: %s", exc)

    # --- Teams ---------------------------------------------------------
    try:
        raw_teams = client.get_teams()
        _save_raw_json(f"{season}_teams", raw_teams)
        _save_csv(dp.teams_to_df(raw_teams), "teams")
    except F1ApiError as exc:
        logger.error("Skipping teams: %s", exc)

    # --- Races (calendar) ----------------------------------------------
    races_df = None
    try:
        raw_races = client.get_races()
        _save_raw_json(f"{season}_races", raw_races)
        races_df = dp.races_to_df(raw_races)
        _save_csv(races_df, "races")
    except F1ApiError as exc:
        logger.error("Skipping races: %s", exc)

    # --- Driver standings ------------------------------------------------
    try:
        raw_driver_standings = client.get_driver_standings()
        _save_raw_json(f"{season}_driver_standings", raw_driver_standings)
        _save_csv(dp.driver_standings_to_df(raw_driver_standings, season), "driver_standings")
    except F1ApiError as exc:
        logger.error("Skipping driver standings: %s", exc)

    # --- Constructor standings -------------------------------------------
    try:
        raw_constructor_standings = client.get_constructor_standings()
        _save_raw_json(f"{season}_constructor_standings", raw_constructor_standings)
        _save_csv(
            dp.constructor_standings_to_df(raw_constructor_standings, season),
            "constructor_standings",
        )
    except F1ApiError as exc:
        logger.error("Skipping constructor standings: %s", exc)

    # --- Race-by-race results (optional, more requests) -------------------
    if fetch_race_results and races_df is not None and not races_df.empty:
        all_results = []
        for round_number in races_df["round"].dropna().astype(int).tolist():
            try:
                raw_result = client.get_race_results(round_number)
                result_df = dp.race_results_to_df(raw_result, season, round_number)
                all_results.append(result_df)
            except F1ApiError as exc:
                logger.error("Skipping results for round %s: %s", round_number, exc)

        if all_results:
            import pandas as pd
            combined = pd.concat(all_results, ignore_index=True)
            _save_csv(combined, "race_results")

    logger.info("Pipeline finished for season=%s", season)

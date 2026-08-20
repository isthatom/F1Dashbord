"""
Entry point for the F1 data pipeline.

Usage:
    python main.py                              # uses config.yaml season range
    python main.py --season 2023                # single season only
    python main.py --start-year 2020 --end-year 2024
    python main.py --no-race-results            # skip per-race results
    python main.py --export-csv                 # also write legacy CSV files

Run this any time you want to refresh data/f1.db for Power BI.
"""

import argparse
import logging

from config.settings import (
    EXPORT_CSV,
    FETCH_RACE_RESULTS,
    SEASON_END_YEAR,
    SEASON_START_YEAR,
)
from src.fetch_data import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch F1 data and prepare it for Power BI.")
    parser.add_argument(
        "--season",
        default=None,
        help="Fetch a single season only (e.g. '2023' or 'current'). "
        "Overrides the season range in config.yaml.",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help=f"First season year to fetch (config default: {SEASON_START_YEAR}).",
    )
    parser.add_argument(
        "--end-year",
        default=None,
        help=f"Last season year to fetch, or 'current' (config default: {SEASON_END_YEAR}).",
    )
    parser.add_argument(
        "--no-race-results",
        action="store_true",
        help="Skip fetching per-race results (fewer API calls, faster run).",
    )
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Also export legacy CSV files to data/processed/ (config can enable this too).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch every requested season, even ones already complete in the database.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed (DEBUG level) logs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    end_year = args.end_year
    if end_year is not None and end_year != "current":
        end_year = int(end_year)

    run(
        season=args.season,
        start_year=args.start_year,
        end_year=end_year,
        fetch_race_results=FETCH_RACE_RESULTS and not args.no_race_results,
        export_csv=args.export_csv or EXPORT_CSV,
        force_refresh=args.force_refresh,
    )


if __name__ == "__main__":
    main()

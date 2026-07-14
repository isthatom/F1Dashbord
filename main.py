"""
Entry point for the F1 data pipeline.

Usage:
    python main.py                     # pulls the current season
    python main.py --season 2023       # pulls a specific season
    python main.py --no-race-results   # skip per-race results (faster)

Run this any time you want to refresh the CSVs that Power BI reads from.
"""

import argparse
import logging

from config.settings import DEFAULT_SEASON
from src.fetch_data import run


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch F1 data and prepare it for Power BI.")
    parser.add_argument(
        "--season",
        default=DEFAULT_SEASON,
        help="Season to fetch, e.g. '2023', or 'current' (default: %(default)s)",
    )
    parser.add_argument(
        "--no-race-results",
        action="store_true",
        help="Skip fetching per-race results (fewer API calls, faster run).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed (DEBUG level) logs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    run(season=args.season, fetch_race_results=not args.no_race_results)


if __name__ == "__main__":
    main()

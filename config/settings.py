"""
Central configuration for the F1 data pipeline.

Keeping all the 'tunable' values (API base URL, season, file paths) in one
place means the rest of the code never hardcodes a URL or a folder path.
If f1api.dev ever changes its base URL, or you want a different season,
this is the only file you should need to touch.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------
BASE_URL = "https://f1api.dev/api"

# Which season to pull. Use "current" for the current season, or a year
# like "2024". Can be overridden with `python main.py --season 2023`.
DEFAULT_SEASON = "current"

REQUEST_TIMEOUT = 15          # seconds, per HTTP request
REQUEST_DELAY = 0.5           # seconds between requests, be polite to a free API
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Folder layout
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"           # untouched JSON straight from the API
PROCESSED_DATA_DIR = DATA_DIR / "processed"  # clean CSVs, ready for Power BI

# Make sure the folders exist even on a fresh clone of the repo
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

"""
Central configuration for the F1 data pipeline.

Values are loaded from config.yaml at the project root. CLI arguments in
main.py can override season range and pipeline toggles at runtime.
"""

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

# ---------------------------------------------------------------------------
# Load config.yaml (with sensible defaults if the file is missing)
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    "api": {
        "base_url": "https://f1api.dev/api",
        "request_timeout": 15,
        "request_delay": 0.5,
        "max_retries": 3,
    },
    "seasons": {
        "start_year": 2018,
        "end_year": "current",
    },
    "pipeline": {
        "fetch_race_results": True,
        "save_raw_json": True,
        "export_csv": False,
    },
}


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return _DEFAULTS.copy()
    with open(CONFIG_PATH, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    # Shallow merge per section so missing keys fall back to defaults
    merged = {}
    for section, defaults in _DEFAULTS.items():
        merged[section] = {**defaults, **(loaded.get(section) or {})}
    return merged


_CONFIG = _load_config()

# ---------------------------------------------------------------------------
# API settings
# ---------------------------------------------------------------------------
BASE_URL: str = _CONFIG["api"]["base_url"]
REQUEST_TIMEOUT: int = int(_CONFIG["api"]["request_timeout"])
REQUEST_DELAY: float = float(_CONFIG["api"]["request_delay"])
MAX_RETRIES: int = int(_CONFIG["api"]["max_retries"])

# ---------------------------------------------------------------------------
# Season settings
# ---------------------------------------------------------------------------
SEASON_START_YEAR: int = int(_CONFIG["seasons"]["start_year"])
_end = _CONFIG["seasons"]["end_year"]
SEASON_END_YEAR: str | int = "current" if str(_end).lower() == "current" else int(_end)

# Kept for backward compatibility with single-season CLI usage
DEFAULT_SEASON: str = "current"

# ---------------------------------------------------------------------------
# Pipeline toggles
# ---------------------------------------------------------------------------
FETCH_RACE_RESULTS: bool = bool(_CONFIG["pipeline"]["fetch_race_results"])
SAVE_RAW_JSON: bool = bool(_CONFIG["pipeline"]["save_raw_json"])
EXPORT_CSV: bool = bool(_CONFIG["pipeline"]["export_csv"])

# ---------------------------------------------------------------------------
# Folder layout
# ---------------------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "f1.db"
LOGS_DIR = PROJECT_ROOT / "logs"
RUN_SUMMARY_PATH = LOGS_DIR / "run_summary.json"

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_season_list(
    *,
    season: str | None = None,
    start_year: int | None = None,
    end_year: str | int | None = None,
) -> list[str]:
    """
    Build the list of season tokens to fetch.

    Priority:
      1. Explicit --season (single season, including "current")
      2. --start-year / --end-year overrides
      3. config.yaml season range
    """
    if season is not None:
        return [season]

    start = start_year if start_year is not None else SEASON_START_YEAR
    end = end_year if end_year is not None else SEASON_END_YEAR

    if str(end).lower() == "current":
        # Historical years plus a final pass for the live season
        return [str(y) for y in range(start, _current_calendar_year())] + ["current"]

    end_int = int(end)
    if end_int < start:
        raise ValueError(f"end_year ({end_int}) must be >= start_year ({start})")
    return [str(y) for y in range(start, end_int + 1)]


def _current_calendar_year() -> int:
    """Best-effort calendar year; refined to the API season when fetching 'current'."""
    from datetime import date
    return date.today().year

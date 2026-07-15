"""
Thin wrapper around the f1api.dev REST API.

Why bother with a wrapper class instead of calling `requests.get` all over
the place? Two reasons, both worth learning as habits:

1. Every API call gets retries, a timeout, and error handling in ONE place.
2. If f1api.dev ever changes a URL path, you fix it here once, not in five
   different scripts.

Docs: https://f1api.dev/docs
"""

import time
import logging
import requests

from config.settings import BASE_URL, REQUEST_TIMEOUT, REQUEST_DELAY, MAX_RETRIES

logger = logging.getLogger(__name__)


class F1ApiError(Exception):
    """Raised when the F1 API can't give us usable data after retries."""


class F1ApiNotFoundError(F1ApiError):
    """Raised when an API resource is not available (HTTP 404)."""


class F1ApiClient:
    """A small, friendly client for f1api.dev."""

    def __init__(self, base_url: str = BASE_URL, season: str = "current"):
        self.base_url = base_url.rstrip("/")
        self.season = season
        self.session = requests.Session()

    # -----------------------------------------------------------------
    # Low-level request helper — everything else calls this
    # -----------------------------------------------------------------
    def _get(self, path: str) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("GET %s (attempt %s/%s)", url, attempt, MAX_RETRIES)
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                time.sleep(REQUEST_DELAY)  # be a good citizen on a free API
                return response.json()
            except requests.exceptions.RequestException as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                # Retrying a missing or invalid resource cannot make it appear.
                # Keep 429 retryable because the API may accept it after backoff.
                if status_code == 404:
                    raise F1ApiNotFoundError(f"Resource not available at {url}") from exc
                if status_code is not None and 400 <= status_code < 500 and status_code != 429:
                    raise F1ApiError(f"Request failed for {url}: {exc}") from exc

                last_error = exc
                logger.warning("Request failed (%s): %s", url, exc)
                time.sleep(1 * attempt)  # simple backoff

        raise F1ApiError(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {last_error}")

    # -----------------------------------------------------------------
    # Public endpoints
    # -----------------------------------------------------------------
    def get_drivers(self, season: str | None = None) -> dict:
        season = season or self.season
        return self._get(f"{season}/drivers")

    def get_teams(self, season: str | None = None) -> dict:
        season = season or self.season
        return self._get(f"{season}/teams")

    def get_races(self, season: str | None = None) -> dict:
        # NOTE: the races endpoint is just /api/{season}, not /api/{season}/races
        # (confirmed against https://f1api.dev/docs/races).
        season = season or self.season
        return self._get(f"{season}")

    def get_driver_standings(self, season: str | None = None) -> dict:
        season = season or self.season
        return self._get(f"{season}/drivers-championship")

    def get_constructor_standings(self, season: str | None = None) -> dict:
        season = season or self.season
        return self._get(f"{season}/constructors-championship")

    def get_race_results(self, round_number: int, season: str | None = None) -> dict:
        season = season or self.season
        return self._get(f"{season}/{round_number}/race")

    def get_latest_race_results(self) -> dict:
        """Return results for the latest completed race in the current season."""
        return self._get("current/last/race")

    def get_circuits(self) -> dict:
        return self._get("circuits")

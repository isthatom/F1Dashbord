"""
Structured run summary written to logs/run_summary.json after each pipeline run.

Console logging is unchanged; this is an additional machine-readable artifact
for monitoring and debugging.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from config.settings import RUN_SUMMARY_PATH

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """Accumulates per-run stats and writes them to JSON."""

    seasons: list[str] = field(default_factory=list)
    tables: dict[str, int] = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)
    _started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _timer_start: float = field(default_factory=perf_counter)

    def set_seasons(self, seasons: list[str]) -> None:
        self.seasons = seasons

    def record_table(self, table: str, rows: int) -> None:
        if rows <= 0:
            return
        self.tables[table] = self.tables.get(table, 0) + rows

    def record_error(
        self,
        message: str,
        *,
        endpoint: str,
        season: str | None = None,
        round_number: int | None = None,
        error_type: str = "F1ApiError",
    ) -> None:
        entry = {
            "endpoint": endpoint,
            "message": str(message),
            "error_type": error_type,
        }
        if season is not None:
            entry["season"] = season
        if round_number is not None:
            entry["round"] = round_number
        self.errors.append(entry)

    def to_dict(self) -> dict:
        duration = perf_counter() - self._timer_start
        return {
            "started_at": self._started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(duration, 2),
            "seasons": self.seasons,
            "tables": self.tables,
            "errors": self.errors,
            "error_count": len(self.errors),
        }

    def write(self, path: Path | None = None) -> Path:
        path = path or RUN_SUMMARY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info("Run summary written -> %s", path)
        return path

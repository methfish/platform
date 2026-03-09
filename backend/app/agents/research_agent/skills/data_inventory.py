"""
Data Inventory skill.

Queries the ohlcv_bars table to catalogue what historical data is
available: symbols, bar counts per symbol/interval pair, and date
ranges.  This is the first skill in the research pipeline and
informs downstream skills about what data exists and what is missing.

Deterministic - no model calls, pure DB queries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)

logger = logging.getLogger(__name__)

# Default symbols and intervals the research pipeline expects to be
# present.  Used to detect gaps when comparing against the DB.
DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AAPL", "MSFT", "SPY"]
DEFAULT_INTERVALS = ["1h", "1d"]


class DataInventorySkill(BaseSkill):
    """Catalogue available OHLCV data in the database."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "data_inventory"

    @property
    def name(self) -> str:
        return "Data Inventory"

    @property
    def description(self) -> str:
        return (
            "Queries the ohlcv_bars table to build an inventory of "
            "available historical data: symbols, bar counts, date ranges, "
            "and identifies gaps that need collection."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    @property
    def required_inputs(self) -> list[str]:
        return ["settings"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        session_factory = ctx.settings.get("session_factory")

        # ----- Path A: Database available --------------------------------
        if session_factory is not None:
            return await self._inventory_from_db(session_factory)

        # ----- Path B: Use collected_data_summary if present -------------
        if ctx.collected_data_summary:
            datasets = ctx.collected_data_summary.get("datasets", [])
            total_bars = ctx.collected_data_summary.get("total_bars", 0)
            gaps = self._detect_gaps(datasets)
            return self._success(
                output={
                    "datasets": datasets,
                    "total_bars": total_bars,
                    "gaps": gaps,
                    "source": "collected_data_summary",
                },
                message=(
                    f"Inventory from context: {len(datasets)} datasets, "
                    f"{total_bars} total bars, {len(gaps)} gaps detected."
                ),
            )

        # ----- Path C: Nothing available ---------------------------------
        gaps = [
            {"symbol": s, "interval": i}
            for s in DEFAULT_SYMBOLS
            for i in DEFAULT_INTERVALS
        ]
        return self._success(
            output={
                "datasets": [],
                "total_bars": 0,
                "gaps": gaps,
                "source": "no_database",
            },
            message=(
                "No database connection available and no context data. "
                "All default symbol/interval pairs flagged as missing - "
                "trigger data collection."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _inventory_from_db(
        self,
        session_factory: Any,
    ) -> SkillResult:
        """Query ohlcv_bars for a complete data inventory."""
        try:
            async with session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT symbol, interval, "
                        "       COUNT(*) AS bar_count, "
                        "       MIN(open_time) AS earliest, "
                        "       MAX(open_time) AS latest "
                        "FROM ohlcv_bars "
                        "GROUP BY symbol, interval "
                        "ORDER BY symbol, interval"
                    )
                )
                rows = result.fetchall()
        except Exception as exc:
            logger.error("Data inventory DB query failed: %s", exc)
            return self._failure(
                message=f"Database query failed: {exc}",
                error_type=type(exc).__name__,
            )

        datasets: list[dict[str, Any]] = []
        total_bars = 0

        for row in rows:
            bar_count = row.bar_count
            total_bars += bar_count
            datasets.append({
                "symbol": row.symbol,
                "interval": row.interval,
                "bar_count": bar_count,
                "earliest": row.earliest.isoformat() if row.earliest else None,
                "latest": row.latest.isoformat() if row.latest else None,
            })

        gaps = self._detect_gaps(datasets)

        return self._success(
            output={
                "datasets": datasets,
                "total_bars": total_bars,
                "gaps": gaps,
                "source": "database",
            },
            message=(
                f"Inventory complete: {len(datasets)} datasets, "
                f"{total_bars} total bars, {len(gaps)} gaps detected."
            ),
        )

    @staticmethod
    def _detect_gaps(
        datasets: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """
        Compare existing datasets against the default symbol/interval
        matrix and return any missing combinations.
        """
        existing = {
            (d["symbol"], d["interval"])
            for d in datasets
        }

        gaps: list[dict[str, str]] = []
        for symbol in DEFAULT_SYMBOLS:
            for interval in DEFAULT_INTERVALS:
                if (symbol, interval) not in existing:
                    gaps.append({"symbol": symbol, "interval": interval})

        # Also flag datasets with suspiciously few bars
        # (less than 50 bars is unlikely to be useful for backtesting)
        for d in datasets:
            if d.get("bar_count", 0) < 50:
                gaps.append({
                    "symbol": d["symbol"],
                    "interval": d["interval"],
                    "reason": f"only {d['bar_count']} bars - insufficient for backtesting",
                })

        return gaps

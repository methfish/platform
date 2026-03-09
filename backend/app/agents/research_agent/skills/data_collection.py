"""
Data Collection skill.

Reads the upstream data_inventory result to identify missing
symbol/interval pairs, then triggers YFinanceCollector to backfill
the gaps.

Deterministic - delegates to the collector, no model calls.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AAPL", "MSFT", "SPY"]
DEFAULT_INTERVALS = ["1h", "1d"]


class DataCollectionSkill(BaseSkill):
    """Collect missing OHLCV data via YFinanceCollector."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "data_collection"

    @property
    def name(self) -> str:
        return "Data Collection"

    @property
    def description(self) -> str:
        return (
            "Reads upstream data_inventory to identify missing data, "
            "then triggers YFinanceCollector to backfill gaps for the "
            "default symbol/interval matrix."
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

    @property
    def prerequisites(self) -> list[str]:
        return ["data_inventory"]

    @property
    def timeout_seconds(self) -> float:
        return 120.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        session_factory = ctx.settings.get("session_factory")
        if session_factory is None:
            return self._skip(
                message=(
                    "No session_factory in settings - cannot persist "
                    "collected data. Skipping data collection."
                ),
            )

        # Determine what to collect from upstream inventory
        symbols_to_collect: list[str] = list(DEFAULT_SYMBOLS)
        intervals_to_collect: list[str] = list(DEFAULT_INTERVALS)

        inventory_result = ctx.upstream_results.get("data_inventory")
        if inventory_result and inventory_result.status == SkillStatus.SUCCESS:
            gaps = inventory_result.output.get("gaps", [])
            if gaps:
                # Collect only the symbols/intervals that are missing
                gap_symbols = {g["symbol"] for g in gaps}
                gap_intervals = {g["interval"] for g in gaps}
                symbols_to_collect = sorted(gap_symbols)
                intervals_to_collect = sorted(gap_intervals)
            else:
                # No gaps found - data is complete
                return self._success(
                    output={
                        "symbols_collected": [],
                        "bars_inserted": 0,
                        "bars_skipped": 0,
                        "message": "No data gaps detected - collection skipped.",
                    },
                    message="All default data already present. No collection needed.",
                )

        # Import collector dependencies
        try:
            from app.data.collector import CollectionJob
            from app.data.yfinance_collector import YFinanceCollector
        except ImportError as exc:
            return self._failure(
                message=f"Failed to import data collection modules: {exc}",
                error_type="ImportError",
            )

        # Create collector and run collection
        try:
            collector = YFinanceCollector()
        except ImportError as exc:
            return self._failure(
                message=f"yfinance not available: {exc}",
                error_type="ImportError",
            )

        job = CollectionJob(
            exchange_id="yfinance",
            symbols=symbols_to_collect,
            intervals=intervals_to_collect,
        )

        try:
            async with session_factory() as session:
                status = await collector.collect(job=job, session=session)
        except Exception as exc:
            logger.error("Data collection failed: %s", exc)
            return self._failure(
                message=f"Data collection failed: {exc}",
                error_type=type(exc).__name__,
            )

        errors = status.errors if status.errors else []
        if status.status == "completed":
            return self._success(
                output={
                    "symbols_collected": symbols_to_collect,
                    "intervals_collected": intervals_to_collect,
                    "bars_inserted": status.bars_inserted,
                    "bars_skipped": status.bars_skipped,
                },
                message=(
                    f"Collected data for {len(symbols_to_collect)} symbols "
                    f"across {len(intervals_to_collect)} intervals. "
                    f"{status.bars_inserted} bars inserted, "
                    f"{status.bars_skipped} skipped."
                ),
            )
        else:
            # completed_with_errors
            return self._success(
                output={
                    "symbols_collected": symbols_to_collect,
                    "intervals_collected": intervals_to_collect,
                    "bars_inserted": status.bars_inserted,
                    "bars_skipped": status.bars_skipped,
                    "errors": errors,
                },
                message=(
                    f"Collection finished with {len(errors)} errors. "
                    f"{status.bars_inserted} bars inserted, "
                    f"{status.bars_skipped} skipped."
                ),
            )

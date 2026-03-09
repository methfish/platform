"""
Backtest Execution skill.

Runs backtests for each strategy type x each symbol found in the
data inventory.  Reads OHLCV bars from the database, converts them
to Bar objects, and feeds them through the BacktestEngine.

Strategy types tested: sma_crossover, rsi, bollinger, macd.

Deterministic - no model calls, pure computation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)

logger = logging.getLogger(__name__)

# Strategies to evaluate in the research pipeline.
RESEARCH_STRATEGIES = ["sma_crossover", "rsi", "bollinger", "macd"]

# Default interval used for backtesting (hourly gives good trade count).
DEFAULT_BACKTEST_INTERVAL = "1h"


class BacktestExecutionSkill(BaseSkill):
    """Run backtests across strategies and symbols."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "backtest_execution"

    @property
    def name(self) -> str:
        return "Backtest Execution"

    @property
    def description(self) -> str:
        return (
            "Runs backtests for each research strategy type against "
            "every symbol found in the data inventory, using the "
            "BacktestEngine with default parameters."
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
        return 300.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        session_factory = ctx.settings.get("session_factory")
        if session_factory is None:
            # Fall back to ctx.backtest_results if available
            if ctx.backtest_results:
                return self._success(
                    output={
                        "backtests_run": len(ctx.backtest_results),
                        "results": ctx.backtest_results,
                        "source": "context",
                    },
                    message=(
                        f"Using {len(ctx.backtest_results)} backtest results "
                        f"from context (no DB connection)."
                    ),
                )
            return self._failure(
                message=(
                    "No session_factory in settings and no backtest_results "
                    "in context. Cannot run backtests."
                ),
            )

        # Determine symbols from upstream data_inventory
        symbols = self._get_symbols_from_inventory(ctx)
        if not symbols:
            return self._failure(
                message="No symbols found in data inventory. Cannot run backtests.",
            )

        # Import engine
        try:
            from app.backtest.engine import BacktestConfig, BacktestEngine, Bar
        except ImportError as exc:
            return self._failure(
                message=f"Failed to import backtest engine: {exc}",
                error_type="ImportError",
            )

        # Run backtests
        all_results: list[dict[str, Any]] = []
        backtests_run = 0

        for symbol in symbols:
            # Load bars from DB
            bars = await self._load_bars(
                session_factory, symbol, DEFAULT_BACKTEST_INTERVAL,
            )
            if not bars or len(bars) < 50:
                logger.warning(
                    "Insufficient data for %s/%s: %d bars (need >= 50). Skipping.",
                    symbol, DEFAULT_BACKTEST_INTERVAL, len(bars) if bars else 0,
                )
                continue

            for strategy_type in RESEARCH_STRATEGIES:
                try:
                    config = BacktestConfig(
                        strategy_type=strategy_type,
                        symbol=symbol,
                        interval=DEFAULT_BACKTEST_INTERVAL,
                        initial_capital=Decimal("10000"),
                        strategy_params={},  # Use defaults
                    )
                    engine = BacktestEngine(config)
                    result = engine.run(bars)
                    backtests_run += 1

                    result_dict: dict[str, Any] = {
                        "strategy": strategy_type,
                        "symbol": symbol,
                        "interval": DEFAULT_BACKTEST_INTERVAL,
                        "status": result.status,
                        "total_bars": result.total_bars,
                        "total_trades": len(result.trades),
                    }

                    if result.metrics:
                        m = result.metrics
                        result_dict.update({
                            "sharpe": round(m.sharpe_ratio, 4),
                            "sortino": round(m.sortino_ratio, 4),
                            "net_pnl": str(m.total_net_pnl),
                            "total_return_pct": round(m.total_return_pct, 4),
                            "max_drawdown_pct": round(m.max_drawdown_pct, 4),
                            "win_rate": round(m.win_rate, 4),
                            "profit_factor": round(m.profit_factor, 4),
                            "total_trades": m.total_trades,
                            "is_trustworthy": m.is_trustworthy,
                            "trust_issues": m.trust_issues,
                        })

                    if result.error:
                        result_dict["error"] = result.error

                    all_results.append(result_dict)

                except Exception as exc:
                    logger.error(
                        "Backtest error for %s/%s: %s",
                        strategy_type, symbol, exc,
                    )
                    all_results.append({
                        "strategy": strategy_type,
                        "symbol": symbol,
                        "interval": DEFAULT_BACKTEST_INTERVAL,
                        "status": "error",
                        "error": str(exc),
                    })
                    backtests_run += 1

        if backtests_run == 0:
            return self._failure(
                message="No backtests were executed - insufficient data for all symbols.",
            )

        return self._success(
            output={
                "backtests_run": backtests_run,
                "results": all_results,
                "source": "database",
            },
            message=(
                f"Executed {backtests_run} backtests across "
                f"{len(symbols)} symbols and "
                f"{len(RESEARCH_STRATEGIES)} strategies."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_symbols_from_inventory(ctx: SkillContext) -> list[str]:
        """Extract unique symbols from upstream data_inventory result."""
        inventory = ctx.upstream_results.get("data_inventory")
        if inventory and inventory.status == SkillStatus.SUCCESS:
            datasets = inventory.output.get("datasets", [])
            # Only include symbols that have data for the backtest interval
            symbols = sorted({
                d["symbol"]
                for d in datasets
                if d.get("interval") == DEFAULT_BACKTEST_INTERVAL
                and d.get("bar_count", 0) >= 50
            })
            if symbols:
                return symbols
            # Fallback: any symbol with enough data
            return sorted({
                d["symbol"]
                for d in datasets
                if d.get("bar_count", 0) >= 50
            })

        # Fallback to ctx.symbols if inventory unavailable
        if ctx.symbols:
            return list(ctx.symbols)

        return []

    @staticmethod
    async def _load_bars(
        session_factory: Any,
        symbol: str,
        interval: str,
    ) -> list[Any]:
        """Load OHLCV bars from DB and convert to Bar objects."""
        from app.backtest.engine import Bar

        try:
            async with session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT symbol, interval, open_time, "
                        "       open, high, low, close, volume "
                        "FROM ohlcv_bars "
                        "WHERE symbol = :symbol AND interval = :interval "
                        "ORDER BY open_time"
                    ),
                    {"symbol": symbol, "interval": interval},
                )
                rows = result.fetchall()
        except Exception as exc:
            logger.error("Failed to load bars for %s/%s: %s", symbol, interval, exc)
            return []

        bars: list[Bar] = []
        for row in rows:
            bars.append(Bar(
                timestamp=row.open_time if row.open_time.tzinfo else row.open_time.replace(tzinfo=timezone.utc),
                open=Decimal(str(row.open)),
                high=Decimal(str(row.high)),
                low=Decimal(str(row.low)),
                close=Decimal(str(row.close)),
                volume=Decimal(str(row.volume)),
                symbol=row.symbol,
                interval=row.interval,
            ))

        return bars

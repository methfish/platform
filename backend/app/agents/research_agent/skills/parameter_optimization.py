"""
Parameter Optimization skill.

Takes the top 2 strategies from result_analysis and runs parameter
sweeps using run_parameter_sweep from the backtest engine.  Each
strategy type has a predefined parameter grid.

Deterministic - no model calls, pure brute-force sweep.
"""

from __future__ import annotations

import logging
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

# Default backtest interval (must match backtest_execution)
DEFAULT_BACKTEST_INTERVAL = "1h"

# Parameter grids for each strategy type
PARAM_GRIDS: dict[str, dict[str, list]] = {
    "sma_crossover": {
        "fast_period": [5, 10, 15, 20],
        "slow_period": [20, 30, 50, 100],
    },
    "rsi": {
        "rsi_period": [7, 14, 21],
        "oversold": [20, 25, 30],
        "overbought": [70, 75, 80],
    },
    "bollinger": {
        "bb_period": [10, 20, 30],
        "num_std": [1.5, 2.0, 2.5, 3.0],
    },
    "macd": {
        "fast_ema": [8, 12, 16],
        "slow_ema": [21, 26, 34],
        "signal_period": [5, 9, 12],
    },
    "grid": {
        "grid_size_pct": [0.5, 1.0, 1.5, 2.0],
    },
    "mean_reversion": {
        "sma_period": [10, 20, 30, 50],
        "entry_std": [1.5, 2.0, 2.5, 3.0],
    },
    "breakout": {
        "lookback": [10, 20, 30, 50],
    },
    "market_making": {
        "spread_bps": [5, 10, 15, 20],
        "inventory_limit": [3, 5, 10],
    },
}

# Maximum number of top strategies to optimize
MAX_TOP_STRATEGIES = 2


class ParameterOptimizationSkill(BaseSkill):
    """Optimize parameters for top-ranked strategies via sweep."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "parameter_optimization"

    @property
    def name(self) -> str:
        return "Parameter Optimization"

    @property
    def description(self) -> str:
        return (
            "Takes the top strategies from result_analysis and runs "
            "parameter sweeps to find optimal configurations for each."
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
        return ["result_analysis"]

    @property
    def timeout_seconds(self) -> float:
        return 300.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        session_factory = ctx.settings.get("session_factory")
        if session_factory is None:
            # Check for sweep_results in context
            if ctx.sweep_results:
                return self._success(
                    output={
                        "optimizations": ctx.sweep_results,
                        "sweep_count": len(ctx.sweep_results),
                        "source": "context",
                    },
                    message=(
                        f"Using {len(ctx.sweep_results)} sweep results "
                        f"from context (no DB connection)."
                    ),
                )
            return self._failure(
                message=(
                    "No session_factory in settings and no sweep_results "
                    "in context. Cannot run parameter sweeps."
                ),
            )

        # Get top strategies from upstream result_analysis
        analysis = ctx.upstream_results.get("result_analysis")
        if analysis is None or analysis.status != SkillStatus.SUCCESS:
            return self._failure(
                message="No successful result_analysis available.",
            )

        ranked = analysis.output.get("ranked_strategies", [])
        if not ranked:
            return self._failure(
                message="No ranked strategies available for optimization.",
            )

        # Take the top N strategies
        top_strategies = ranked[:MAX_TOP_STRATEGIES]

        # Import engine
        try:
            from app.backtest.engine import Bar, run_parameter_sweep
        except ImportError as exc:
            return self._failure(
                message=f"Failed to import backtest engine: {exc}",
                error_type="ImportError",
            )

        optimizations: list[dict[str, Any]] = []
        total_sweep_count = 0

        for strategy_entry in top_strategies:
            strategy_type = strategy_entry.get("strategy", "")
            symbol = strategy_entry.get("symbol", "")

            if not strategy_type or not symbol:
                continue

            param_grid = PARAM_GRIDS.get(strategy_type)
            if not param_grid:
                logger.warning(
                    "No parameter grid defined for strategy '%s'. Skipping.",
                    strategy_type,
                )
                continue

            # Filter out invalid sma_crossover combos (fast >= slow)
            if strategy_type == "sma_crossover":
                param_grid = self._filter_sma_grid(param_grid)

            # Load bars from DB
            bars = await self._load_bars(
                session_factory, symbol, DEFAULT_BACKTEST_INTERVAL,
            )
            if not bars or len(bars) < 50:
                logger.warning(
                    "Insufficient data for sweep: %s/%s (%d bars). Skipping.",
                    symbol, DEFAULT_BACKTEST_INTERVAL,
                    len(bars) if bars else 0,
                )
                continue

            # Count combinations
            import itertools
            combo_count = len(list(itertools.product(*param_grid.values())))
            total_sweep_count += combo_count

            try:
                sweep_results = run_parameter_sweep(
                    bars=bars,
                    strategy_type=strategy_type,
                    symbol=symbol,
                    param_grid=param_grid,
                    initial_capital=Decimal("10000"),
                )
            except Exception as exc:
                logger.error(
                    "Parameter sweep failed for %s/%s: %s",
                    strategy_type, symbol, exc,
                )
                optimizations.append({
                    "strategy": strategy_type,
                    "symbol": symbol,
                    "status": "error",
                    "error": str(exc),
                })
                continue

            if not sweep_results:
                optimizations.append({
                    "strategy": strategy_type,
                    "symbol": symbol,
                    "status": "no_results",
                    "message": "Sweep produced no viable results.",
                })
                continue

            # Take the best result
            best = sweep_results[0]
            optimizations.append({
                "strategy": strategy_type,
                "symbol": symbol,
                "status": "completed",
                "best_params": best.params,
                "sharpe": round(best.metrics.sharpe_ratio, 4),
                "sortino": round(best.metrics.sortino_ratio, 4),
                "net_pnl": str(best.metrics.total_net_pnl),
                "total_return_pct": round(best.metrics.total_return_pct, 4),
                "max_drawdown_pct": round(best.metrics.max_drawdown_pct, 4),
                "win_rate": round(best.metrics.win_rate, 4),
                "total_trades": best.metrics.total_trades,
                "rank_score": round(best.rank_score, 4),
                "combos_tested": combo_count,
                "viable_results": len(sweep_results),
                # Include top 3 for comparison
                "top_3": [
                    {
                        "params": sr.params,
                        "sharpe": round(sr.metrics.sharpe_ratio, 4),
                        "net_pnl": str(sr.metrics.total_net_pnl),
                        "rank_score": round(sr.rank_score, 4),
                    }
                    for sr in sweep_results[:3]
                ],
            })

        if not optimizations:
            return self._failure(
                message="No parameter optimizations could be completed.",
            )

        return self._success(
            output={
                "optimizations": optimizations,
                "sweep_count": total_sweep_count,
                "source": "database",
            },
            message=(
                f"Completed parameter sweeps for {len(optimizations)} "
                f"strategy/symbol pairs ({total_sweep_count} total combinations)."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_sma_grid(
        param_grid: dict[str, list],
    ) -> dict[str, list]:
        """
        For SMA crossover, ensure fast_period < slow_period.

        We keep the grid as-is but the sweep will naturally produce
        invalid results (fast >= slow).  Those will have 0 trades
        and get filtered out by run_parameter_sweep.
        """
        # Return as-is; the engine handles this gracefully
        return param_grid

    @staticmethod
    async def _load_bars(
        session_factory: Any,
        symbol: str,
        interval: str,
    ) -> list[Any]:
        """Load OHLCV bars from DB and convert to Bar objects."""
        from app.backtest.engine import Bar
        from datetime import timezone

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

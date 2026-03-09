"""
Result Analysis skill.

Reads backtest results from the upstream backtest_execution skill,
ranks strategies by Sharpe ratio, and flags trust issues such as
too few trades or excessive drawdown.

Hybrid - primarily deterministic ranking logic but could be extended
with model-assisted commentary.
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

# Trust thresholds
MIN_TRADES_THRESHOLD = 10
MAX_DRAWDOWN_THRESHOLD = 30.0  # percent
MIN_PROFIT_FACTOR = 0.5
MIN_WIN_RATE = 0.2


class ResultAnalysisSkill(BaseSkill):
    """Rank and analyse backtest results for strategy selection."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "result_analysis"

    @property
    def name(self) -> str:
        return "Result Analysis"

    @property
    def description(self) -> str:
        return (
            "Ranks backtest results by Sharpe ratio, flags trust issues "
            "(too few trades, excessive drawdown, low win rate), and "
            "identifies best/worst strategies."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.HYBRID

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    @property
    def required_inputs(self) -> list[str]:
        return []

    @property
    def prerequisites(self) -> list[str]:
        return ["backtest_execution"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Get backtest results from upstream
        bt_result = ctx.upstream_results.get("backtest_execution")
        if bt_result is None or bt_result.status != SkillStatus.SUCCESS:
            return self._failure(
                message="No successful backtest_execution results available.",
            )

        raw_results = bt_result.output.get("results", [])
        if not raw_results:
            return self._failure(
                message="Backtest execution produced no results to analyse.",
            )

        # Filter to completed results that have metrics
        completed = [
            r for r in raw_results
            if r.get("status") == "completed" and r.get("sharpe") is not None
        ]

        if not completed:
            return self._failure(
                message="No completed backtests with metrics found.",
            )

        # Rank by Sharpe ratio (descending)
        ranked = sorted(
            completed,
            key=lambda r: r.get("sharpe", 0.0),
            reverse=True,
        )

        # Annotate each result with trust flags
        ranked_strategies: list[dict[str, Any]] = []
        all_trust_flags: list[dict[str, Any]] = []

        for rank_idx, result in enumerate(ranked):
            flags = self._assess_trust(result)
            entry: dict[str, Any] = {
                "rank": rank_idx + 1,
                "strategy": result.get("strategy", "unknown"),
                "symbol": result.get("symbol", "unknown"),
                "sharpe": result.get("sharpe", 0.0),
                "sortino": result.get("sortino", 0.0),
                "net_pnl": result.get("net_pnl", "0"),
                "total_return_pct": result.get("total_return_pct", 0.0),
                "max_drawdown_pct": result.get("max_drawdown_pct", 0.0),
                "win_rate": result.get("win_rate", 0.0),
                "profit_factor": result.get("profit_factor", 0.0),
                "total_trades": result.get("total_trades", 0),
                "is_trustworthy": len(flags) == 0,
                "trust_flags": flags,
            }
            ranked_strategies.append(entry)

            if flags:
                all_trust_flags.append({
                    "strategy": result.get("strategy"),
                    "symbol": result.get("symbol"),
                    "flags": flags,
                })

        best = ranked_strategies[0] if ranked_strategies else {}
        worst = ranked_strategies[-1] if ranked_strategies else {}

        # Summary statistics
        sharpe_values = [r.get("sharpe", 0.0) for r in ranked]
        avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0.0
        profitable_count = sum(
            1 for r in ranked
            if float(r.get("net_pnl", "0")) > 0
        )

        return self._success(
            output={
                "ranked_strategies": ranked_strategies,
                "trust_flags": all_trust_flags,
                "best_strategy": best,
                "worst_strategy": worst,
                "summary": {
                    "total_evaluated": len(ranked_strategies),
                    "profitable_strategies": profitable_count,
                    "avg_sharpe": round(avg_sharpe, 4),
                    "trustworthy_count": sum(
                        1 for r in ranked_strategies if r["is_trustworthy"]
                    ),
                },
            },
            message=(
                f"Analysed {len(ranked_strategies)} strategies. "
                f"Best: {best.get('strategy')}/{best.get('symbol')} "
                f"(Sharpe={best.get('sharpe', 0.0):.4f}). "
                f"{profitable_count}/{len(ranked_strategies)} profitable."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assess_trust(result: dict[str, Any]) -> list[str]:
        """
        Evaluate a single backtest result for trust issues.

        Returns a list of human-readable flag strings.
        """
        flags: list[str] = []

        total_trades = result.get("total_trades", 0)
        if total_trades < MIN_TRADES_THRESHOLD:
            flags.append(
                f"Too few trades ({total_trades} < {MIN_TRADES_THRESHOLD})"
            )

        max_dd = abs(result.get("max_drawdown_pct", 0.0))
        if max_dd > MAX_DRAWDOWN_THRESHOLD:
            flags.append(
                f"Excessive drawdown ({max_dd:.1f}% > {MAX_DRAWDOWN_THRESHOLD}%)"
            )

        profit_factor = result.get("profit_factor", 0.0)
        if 0 < profit_factor < MIN_PROFIT_FACTOR and total_trades >= MIN_TRADES_THRESHOLD:
            flags.append(
                f"Low profit factor ({profit_factor:.2f} < {MIN_PROFIT_FACTOR})"
            )

        win_rate = result.get("win_rate", 0.0)
        if win_rate < MIN_WIN_RATE and total_trades >= MIN_TRADES_THRESHOLD:
            flags.append(
                f"Low win rate ({win_rate:.1%} < {MIN_WIN_RATE:.0%})"
            )

        sharpe = result.get("sharpe", 0.0)
        if sharpe < -1.0:
            flags.append(
                f"Very negative Sharpe ratio ({sharpe:.2f})"
            )

        # Check for upstream trust issues reported by the backtest engine
        engine_flags = result.get("trust_issues", [])
        if engine_flags:
            flags.extend(engine_flags)

        return flags

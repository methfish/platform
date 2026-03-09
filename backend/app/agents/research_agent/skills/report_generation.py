"""
Report Generation skill.

Compiles a structured research report from all upstream skill results.
Aggregates data inventory status, backtest summaries, strategy rankings,
and optimization results into a single cohesive output.

Model-assisted - the report structure is deterministic but could be
extended with LLM-generated narrative summaries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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


class ReportGenerationSkill(BaseSkill):
    """Compile a structured research report from upstream results."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "report_generation"

    @property
    def name(self) -> str:
        return "Report Generation"

    @property
    def description(self) -> str:
        return (
            "Compiles a structured research report from all upstream "
            "skill results, including data status, backtest summaries, "
            "strategy rankings, and optimization outcomes."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.MODEL_ASSISTED

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    @property
    def required_inputs(self) -> list[str]:
        return []

    @property
    def prerequisites(self) -> list[str]:
        return ["result_analysis"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # --- 1. Summary -------------------------------------------------
        report["summary"] = self._build_summary(ctx)

        # --- 2. Data status ---------------------------------------------
        report["data_status"] = self._build_data_status(ctx)

        # --- 3. Backtest summary ----------------------------------------
        report["backtest_summary"] = self._build_backtest_summary(ctx)

        # --- 4. Top strategies ------------------------------------------
        report["top_strategies"] = self._build_top_strategies(ctx)

        # --- 5. Optimization results ------------------------------------
        report["optimization_results"] = self._build_optimization_results(ctx)

        # --- 6. Recommendations -----------------------------------------
        report["recommendations"] = self._build_recommendations(ctx)

        # Build the overall summary line
        top_strats = report["top_strategies"]
        opt_results = report["optimization_results"]
        summary_line = (
            f"Research report generated. "
            f"{len(top_strats)} strategies ranked"
        )
        if opt_results:
            summary_line += f", {len(opt_results)} optimized"
        summary_line += "."

        return self._success(
            output={"report": report},
            message=summary_line,
        )

    # ------------------------------------------------------------------
    # Report section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(ctx: SkillContext) -> str:
        """Build a one-paragraph executive summary."""
        parts: list[str] = []

        # Data inventory summary
        inv = ctx.upstream_results.get("data_inventory")
        if inv and inv.status == SkillStatus.SUCCESS:
            total_bars = inv.output.get("total_bars", 0)
            datasets = inv.output.get("datasets", [])
            symbols = sorted({d["symbol"] for d in datasets})
            parts.append(
                f"Data inventory contains {total_bars} bars across "
                f"{len(datasets)} datasets covering {len(symbols)} symbols."
            )

        # Backtest summary
        bt = ctx.upstream_results.get("backtest_execution")
        if bt and bt.status == SkillStatus.SUCCESS:
            backtests_run = bt.output.get("backtests_run", 0)
            parts.append(f"{backtests_run} backtests were executed.")

        # Analysis summary
        analysis = ctx.upstream_results.get("result_analysis")
        if analysis and analysis.status == SkillStatus.SUCCESS:
            summary_data = analysis.output.get("summary", {})
            profitable = summary_data.get("profitable_strategies", 0)
            total = summary_data.get("total_evaluated", 0)
            avg_sharpe = summary_data.get("avg_sharpe", 0.0)
            parts.append(
                f"{profitable}/{total} strategies were profitable "
                f"(avg Sharpe: {avg_sharpe:.4f})."
            )

            best = analysis.output.get("best_strategy", {})
            if best:
                parts.append(
                    f"Best performing: {best.get('strategy')}/{best.get('symbol')} "
                    f"with Sharpe {best.get('sharpe', 0.0):.4f}."
                )

        # Optimization summary
        opt = ctx.upstream_results.get("parameter_optimization")
        if opt and opt.status == SkillStatus.SUCCESS:
            optimizations = opt.output.get("optimizations", [])
            completed_opts = [o for o in optimizations if o.get("status") == "completed"]
            if completed_opts:
                best_opt = max(
                    completed_opts,
                    key=lambda o: o.get("sharpe", 0.0),
                )
                parts.append(
                    f"Parameter optimization improved best strategy to "
                    f"Sharpe {best_opt.get('sharpe', 0.0):.4f} "
                    f"({best_opt.get('strategy')}/{best_opt.get('symbol')})."
                )

        return " ".join(parts) if parts else "No upstream data available for summary."

    @staticmethod
    def _build_data_status(ctx: SkillContext) -> dict[str, Any]:
        """Extract data inventory status."""
        inv = ctx.upstream_results.get("data_inventory")
        if inv and inv.status == SkillStatus.SUCCESS:
            return {
                "total_bars": inv.output.get("total_bars", 0),
                "datasets_count": len(inv.output.get("datasets", [])),
                "gaps_count": len(inv.output.get("gaps", [])),
                "gaps": inv.output.get("gaps", []),
                "source": inv.output.get("source", "unknown"),
            }

        collection = ctx.upstream_results.get("data_collection")
        if collection and collection.status == SkillStatus.SUCCESS:
            return {
                "bars_inserted": collection.output.get("bars_inserted", 0),
                "bars_skipped": collection.output.get("bars_skipped", 0),
                "symbols_collected": collection.output.get("symbols_collected", []),
                "source": "data_collection",
            }

        return {"status": "no_data_available"}

    @staticmethod
    def _build_backtest_summary(ctx: SkillContext) -> dict[str, Any]:
        """Summarize backtest execution results."""
        bt = ctx.upstream_results.get("backtest_execution")
        if not bt or bt.status != SkillStatus.SUCCESS:
            return {"status": "not_run"}

        results = bt.output.get("results", [])
        completed = [r for r in results if r.get("status") == "completed"]
        errored = [r for r in results if r.get("status") == "error"]

        strategies_tested = sorted({r.get("strategy", "") for r in results})
        symbols_tested = sorted({r.get("symbol", "") for r in results})

        return {
            "backtests_run": bt.output.get("backtests_run", 0),
            "completed": len(completed),
            "errored": len(errored),
            "strategies_tested": strategies_tested,
            "symbols_tested": symbols_tested,
            "source": bt.output.get("source", "unknown"),
        }

    @staticmethod
    def _build_top_strategies(ctx: SkillContext) -> list[dict[str, Any]]:
        """Extract ranked strategies from result_analysis."""
        analysis = ctx.upstream_results.get("result_analysis")
        if not analysis or analysis.status != SkillStatus.SUCCESS:
            return []

        ranked = analysis.output.get("ranked_strategies", [])

        # Return top 5 strategies with key metrics
        top: list[dict[str, Any]] = []
        for entry in ranked[:5]:
            top.append({
                "rank": entry.get("rank"),
                "strategy": entry.get("strategy"),
                "symbol": entry.get("symbol"),
                "sharpe": entry.get("sharpe"),
                "net_pnl": entry.get("net_pnl"),
                "total_return_pct": entry.get("total_return_pct"),
                "max_drawdown_pct": entry.get("max_drawdown_pct"),
                "win_rate": entry.get("win_rate"),
                "total_trades": entry.get("total_trades"),
                "is_trustworthy": entry.get("is_trustworthy"),
                "trust_flags": entry.get("trust_flags", []),
            })

        return top

    @staticmethod
    def _build_optimization_results(ctx: SkillContext) -> list[dict[str, Any]]:
        """Extract parameter optimization outcomes."""
        opt = ctx.upstream_results.get("parameter_optimization")
        if not opt or opt.status != SkillStatus.SUCCESS:
            return []

        optimizations = opt.output.get("optimizations", [])
        results: list[dict[str, Any]] = []

        for entry in optimizations:
            if entry.get("status") != "completed":
                results.append({
                    "strategy": entry.get("strategy"),
                    "symbol": entry.get("symbol"),
                    "status": entry.get("status"),
                    "error": entry.get("error", ""),
                })
                continue

            results.append({
                "strategy": entry.get("strategy"),
                "symbol": entry.get("symbol"),
                "status": "completed",
                "best_params": entry.get("best_params", {}),
                "sharpe": entry.get("sharpe"),
                "net_pnl": entry.get("net_pnl"),
                "total_return_pct": entry.get("total_return_pct"),
                "max_drawdown_pct": entry.get("max_drawdown_pct"),
                "win_rate": entry.get("win_rate"),
                "total_trades": entry.get("total_trades"),
                "combos_tested": entry.get("combos_tested"),
                "top_3": entry.get("top_3", []),
            })

        return results

    @staticmethod
    def _build_recommendations(ctx: SkillContext) -> list[str]:
        """
        Generate actionable recommendations based on all upstream results.

        Returns a list of human-readable recommendation strings.
        """
        recommendations: list[str] = []

        # --- Data recommendations ---
        inv = ctx.upstream_results.get("data_inventory")
        if inv and inv.status == SkillStatus.SUCCESS:
            gaps = inv.output.get("gaps", [])
            if gaps:
                gap_symbols = sorted({g["symbol"] for g in gaps})
                recommendations.append(
                    f"Collect missing data for: {', '.join(gap_symbols)}. "
                    f"{len(gaps)} symbol/interval gaps remain."
                )

        # --- Strategy recommendations ---
        analysis = ctx.upstream_results.get("result_analysis")
        if analysis and analysis.status == SkillStatus.SUCCESS:
            ranked = analysis.output.get("ranked_strategies", [])
            trustworthy = [r for r in ranked if r.get("is_trustworthy")]
            untrustworthy = [r for r in ranked if not r.get("is_trustworthy")]

            if not trustworthy:
                recommendations.append(
                    "No strategies passed all trust checks. Consider "
                    "collecting more data or adjusting strategy parameters."
                )
            elif len(trustworthy) == 1:
                s = trustworthy[0]
                recommendations.append(
                    f"Only one trustworthy strategy found: "
                    f"{s['strategy']}/{s['symbol']} (Sharpe={s['sharpe']:.4f}). "
                    f"Consider diversifying with additional strategy types."
                )
            else:
                recommendations.append(
                    f"{len(trustworthy)} trustworthy strategies identified. "
                    f"Consider deploying the top 2-3 in paper trading mode."
                )

            if untrustworthy:
                # Summarize the most common trust issue
                all_flags: list[str] = []
                for r in untrustworthy:
                    all_flags.extend(r.get("trust_flags", []))
                if all_flags:
                    # Find the most common flag prefix
                    flag_categories: dict[str, int] = {}
                    for flag in all_flags:
                        category = flag.split("(")[0].strip()
                        flag_categories[category] = flag_categories.get(category, 0) + 1
                    most_common = max(flag_categories, key=flag_categories.get)  # type: ignore[arg-type]
                    recommendations.append(
                        f"Most common trust issue: '{most_common}' "
                        f"({flag_categories[most_common]} occurrences). "
                        f"Address this to improve strategy reliability."
                    )

        # --- Optimization recommendations ---
        opt = ctx.upstream_results.get("parameter_optimization")
        if opt and opt.status == SkillStatus.SUCCESS:
            optimizations = opt.output.get("optimizations", [])
            completed = [o for o in optimizations if o.get("status") == "completed"]

            if completed:
                # Compare optimized vs default parameters
                for o in completed:
                    default_sharpe = None
                    # Look up the default Sharpe from the analysis
                    if analysis and analysis.status == SkillStatus.SUCCESS:
                        for r in analysis.output.get("ranked_strategies", []):
                            if (r.get("strategy") == o.get("strategy") and
                                    r.get("symbol") == o.get("symbol")):
                                default_sharpe = r.get("sharpe", 0.0)
                                break

                    opt_sharpe = o.get("sharpe", 0.0)
                    if default_sharpe is not None and opt_sharpe > default_sharpe:
                        improvement = opt_sharpe - default_sharpe
                        recommendations.append(
                            f"Optimization improved {o['strategy']}/{o['symbol']} "
                            f"Sharpe by {improvement:.4f} "
                            f"({default_sharpe:.4f} -> {opt_sharpe:.4f}). "
                            f"Use optimized params: {o.get('best_params', {})}."
                        )
                    elif default_sharpe is not None:
                        recommendations.append(
                            f"Optimization did not improve {o['strategy']}/{o['symbol']} "
                            f"(default Sharpe {default_sharpe:.4f} >= optimized {opt_sharpe:.4f}). "
                            f"Default parameters may be sufficient."
                        )

        # --- General recommendations ---
        if not recommendations:
            recommendations.append(
                "Insufficient upstream data to generate recommendations. "
                "Ensure the full pipeline (data_inventory through "
                "result_analysis) completes successfully."
            )

        return recommendations

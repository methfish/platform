"""
Trade Decision skill.

Assembles the final trade decision from all upstream outputs:
opportunity scores, allocations, entry plans, and risk precheck
results.

The decision is either "TRADE" (with selected orders) or
"NO_TRADE" (with reasoning).

HYBRID execution type - deterministic assembly with the option
for model-augmented confidence scoring.
"""

from __future__ import annotations

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)


class TradeDecisionSkill(BaseSkill):
    """Assemble the final TRADE or NO_TRADE decision."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "trade_decision"

    @property
    def name(self) -> str:
        return "Trade Decision"

    @property
    def description(self) -> str:
        return (
            "Assembles the final trade decision from opportunity scores, "
            "allocations, entry plans, and risk precheck results."
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
        return SkillRiskLevel.HIGH

    @property
    def prerequisites(self) -> list[str]:
        return ["risk_precheck"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        reasons: list[str] = []

        # --- Read upstream results ---
        scoring_result = ctx.upstream_results.get("opportunity_scoring")
        precheck_result = ctx.upstream_results.get("risk_precheck")
        sizing_result = ctx.upstream_results.get("position_sizing")

        # --- Check: risk precheck denied all orders ---
        if precheck_result and precheck_result.status == SkillStatus.FAILURE:
            reasons.append("Risk precheck denied all planned orders.")
            return self._no_trade(reasons, ctx)

        # --- Check: opportunity scoring flagged no trade ---
        if scoring_result:
            no_trade = scoring_result.output.get("no_trade", False)
            if no_trade:
                reasons.append(
                    "All opportunity scores below minimum threshold "
                    f"({scoring_result.output.get('threshold', 30)})."
                )
                return self._no_trade(reasons, ctx)

        # --- Check: no allocations produced ---
        if sizing_result:
            allocations = sizing_result.output.get("allocations", {})
            if not allocations:
                reasons.append("No allocations produced by position sizing.")
                return self._no_trade(reasons, ctx)

        # --- Assemble selected orders from risk-checked plans ---
        selected_orders: list[dict] = []
        if precheck_result and precheck_result.status == SkillStatus.SUCCESS:
            checked_orders = precheck_result.output.get("checked_orders", [])
            selected_orders = [
                co for co in checked_orders if co.get("allowed", False)
            ]

        if not selected_orders:
            reasons.append("No orders survived risk precheck.")
            return self._no_trade(reasons, ctx)

        # --- Build reasoning summary ---
        best_score = (
            scoring_result.output.get("best_score", 0)
            if scoring_result
            else 0
        )
        reasoning_parts = [
            f"{len(selected_orders)} order(s) selected.",
            f"Best opportunity score: {best_score}.",
        ]
        if precheck_result:
            denied = precheck_result.output.get("denied_count", 0)
            if denied > 0:
                reasoning_parts.append(f"{denied} order(s) denied by risk rules.")

        # Confidence: blend of opportunity score and risk gate pass rate.
        total_checked = len(
            precheck_result.output.get("checked_orders", [])
        ) if precheck_result else 1
        pass_rate = len(selected_orders) / max(total_checked, 1)
        confidence = min(
            (best_score / 100) * 0.6 + pass_rate * 0.4, 1.0,
        )

        return self._success(
            output={
                "decision": "TRADE",
                "selected_orders": selected_orders,
                "confidence": round(confidence, 4),
                "reasoning_summary": " ".join(reasoning_parts),
            },
            message=f"TRADE decision: {len(selected_orders)} orders.",
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _no_trade(
        self,
        reasons: list[str],
        ctx: SkillContext,
    ) -> SkillResult:
        """Build a NO_TRADE decision result."""
        return self._success(
            output={
                "decision": "NO_TRADE",
                "selected_orders": [],
                "confidence": 1.0,
                "reasoning_summary": " ".join(reasons),
            },
            message=f"NO_TRADE: {' '.join(reasons)}",
            confidence=1.0,
        )

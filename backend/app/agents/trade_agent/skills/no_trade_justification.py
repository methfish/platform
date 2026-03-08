"""
No-Trade Justification skill.

Only produces substantive output when the trade decision is
"NO_TRADE". If the decision was "TRADE", this skill skips.

Generates a structured justification: blocked symbols, limiting
factors, and a suggested next review time.

MODEL_ASSISTED execution type - the justification narrative can
be augmented by an LLM for richer explanations.
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


class NoTradeJustificationSkill(BaseSkill):
    """Generate structured justification when trade decision is NO_TRADE."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "no_trade_justification"

    @property
    def name(self) -> str:
        return "No-Trade Justification"

    @property
    def description(self) -> str:
        return (
            "Produces structured justification when the pipeline "
            "decides not to trade: blocked symbols, limiting factors, "
            "and next review suggestion."
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
    def prerequisites(self) -> list[str]:
        return ["trade_decision"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        decision_result = ctx.upstream_results["trade_decision"]
        decision = decision_result.output.get("decision", "")

        # If the decision was TRADE, skip entirely.
        if decision == "TRADE":
            return self._skip("Decision was TRADE - no justification needed.")

        # --- Gather limiting factors from upstream results ---
        reasons: list[str] = []
        blocked_symbols: list[str] = []
        limiting_factors: list[str] = []

        # From trade decision reasoning.
        reasoning_summary = decision_result.output.get("reasoning_summary", "")
        if reasoning_summary:
            reasons.append(reasoning_summary)

        # From opportunity scoring.
        scoring_result = ctx.upstream_results.get("opportunity_scoring")
        if scoring_result and scoring_result.status == SkillStatus.SUCCESS:
            candidates = scoring_result.output.get("ranked_candidates", [])
            threshold = scoring_result.output.get("threshold", 30)
            for c in candidates:
                if c["score"] < threshold:
                    blocked_symbols.append(c["symbol"])
                    limiting_factors.append(
                        f"{c['symbol']}: score {c['score']} below threshold {threshold}"
                    )

        # From risk precheck.
        precheck_result = ctx.upstream_results.get("risk_precheck")
        if precheck_result:
            triggered = (
                precheck_result.output.get("triggered_rules", [])
                if precheck_result.status == SkillStatus.SUCCESS
                else precheck_result.details.get("triggered_rules", [])
            )
            for rule in triggered:
                symbol = rule.get("symbol", "unknown")
                if symbol not in blocked_symbols:
                    blocked_symbols.append(symbol)
                violations = rule.get("violations", [])
                for v in violations:
                    limiting_factors.append(f"{symbol}: {v}")

        # From market context - low liquidity.
        market_result = ctx.upstream_results.get("market_context")
        if market_result and market_result.status == SkillStatus.SUCCESS:
            for sc in market_result.output.get("symbol_contexts", []):
                if sc.get("low_liquidity"):
                    factor = f"{sc['symbol']}: low liquidity (vol={sc['volume_24h']})"
                    if factor not in limiting_factors:
                        limiting_factors.append(factor)

        # Suggest next review.
        next_review_suggestion = self._suggest_next_review(limiting_factors)

        return self._success(
            output={
                "reasons": reasons,
                "blocked_symbols": blocked_symbols,
                "limiting_factors": limiting_factors,
                "next_review_suggestion": next_review_suggestion,
            },
            message=(
                f"No-trade justification: {len(blocked_symbols)} blocked symbols, "
                f"{len(limiting_factors)} limiting factors."
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest_next_review(limiting_factors: list[str]) -> str:
        """
        Suggest when to review next based on the nature of limiting
        factors.
        """
        has_kill_switch = any("kill_switch" in f for f in limiting_factors)
        has_liquidity = any("low_liquidity" in f or "liquidity" in f for f in limiting_factors)
        has_score = any("score" in f and "below" in f for f in limiting_factors)

        if has_kill_switch:
            return "Review after kill switch is manually cleared."

        if has_liquidity:
            return "Review in 1 hour when liquidity may improve."

        if has_score:
            return "Review in 15 minutes for updated market conditions."

        return "Review at next scheduled pipeline cycle."

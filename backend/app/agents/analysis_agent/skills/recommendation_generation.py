"""
Recommendation Generation Skill - Produces actionable recommendations.

Synthesises root cause classifications and counterfactual scenarios
into concrete recommendations that can improve future trading outcomes.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
)

logger = logging.getLogger(__name__)

# Recommendation type constants.
REC_RISK_CONFIG = "risk_config_change"
REC_SIZING = "sizing_change"
REC_EXECUTION = "execution_change"
REC_MONITORING = "monitoring_change"
REC_NO_CHANGE = "no_change"

# Mapping from root-cause category to default recommendation type.
_CATEGORY_TO_REC_TYPE: dict[str, str] = {
    "market": REC_NO_CHANGE,
    "model": REC_MONITORING,
    "sizing": REC_SIZING,
    "execution": REC_EXECUTION,
    "exchange": REC_MONITORING,
    "data": REC_MONITORING,
    "risk_control": REC_RISK_CONFIG,
    "system_bug": REC_MONITORING,
    "unknown": REC_NO_CHANGE,
}

# Canned recommendation descriptions per category.
_CATEGORY_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "exchange": {
        "type": REC_MONITORING,
        "description": (
            "Add exchange health monitoring alerts and implement automatic "
            "back-off on repeated exchange errors."
        ),
        "priority": "high",
        "expected_benefit": "Reduced order failures during exchange degradation.",
    },
    "risk_control": {
        "type": REC_RISK_CONFIG,
        "description": (
            "Review risk thresholds and circuit-breaker settings. Consider "
            "tightening position limits or adjusting drawdown thresholds."
        ),
        "priority": "high",
        "expected_benefit": "Fewer risk-triggered rejections and smaller tail losses.",
    },
    "sizing": {
        "type": REC_SIZING,
        "description": (
            "Reduce default position sizing or implement dynamic sizing "
            "based on current volatility and liquidity."
        ),
        "priority": "high",
        "expected_benefit": "Lower impact per trade and reduced slippage.",
    },
    "execution": {
        "type": REC_EXECUTION,
        "description": (
            "Switch to limit orders where possible and implement adaptive "
            "slippage thresholds tied to current spread."
        ),
        "priority": "medium",
        "expected_benefit": "Better fill quality and reduced execution costs.",
    },
    "market": {
        "type": REC_NO_CHANGE,
        "description": (
            "Loss driven by adverse market movement; no configuration "
            "change needed unless pattern is systematic."
        ),
        "priority": "low",
        "expected_benefit": "N/A - market risk is inherent.",
    },
    "model": {
        "type": REC_MONITORING,
        "description": (
            "Add model performance monitoring and consider retraining or "
            "disabling model signals during regime changes."
        ),
        "priority": "medium",
        "expected_benefit": "Earlier detection of model degradation.",
    },
    "data": {
        "type": REC_MONITORING,
        "description": (
            "Add data freshness checks and fallback data sources. Implement "
            "staleness alerts for market data feeds."
        ),
        "priority": "high",
        "expected_benefit": "Avoid trading on stale or missing data.",
    },
    "system_bug": {
        "type": REC_MONITORING,
        "description": (
            "File a bug report and add regression tests. Implement "
            "additional assertions and error handling."
        ),
        "priority": "critical",
        "expected_benefit": "Prevent recurrence of the same software defect.",
    },
    "unknown": {
        "type": REC_NO_CHANGE,
        "description": (
            "Root cause is unclear. Manual investigation recommended. "
            "No automated change advisable."
        ),
        "priority": "low",
        "expected_benefit": "N/A - insufficient information.",
    },
}


class RecommendationGenerationSkill(BaseSkill):
    """Model-assisted recommendation generator requiring human review."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "recommendation_generation"

    @property
    def name(self) -> str:
        return "Recommendation Generation"

    @property
    def description(self) -> str:
        return (
            "Generates actionable recommendations based on root causes "
            "and counterfactual analysis."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.MODEL_ASSISTED

    @property
    def required_inputs(self) -> list[str]:
        return []

    @property
    def prerequisites(self) -> list[str]:
        return ["counterfactual_analysis"]

    @property
    def requires_human_review(self) -> bool:
        return True

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Gather root causes.
        rc_result = ctx.upstream_results.get("root_cause_classification")
        root_causes: list[dict[str, Any]] = []
        if rc_result and rc_result.output:
            root_causes = rc_result.output.get("root_causes", [])

        # Gather counterfactual scenarios.
        cf_result = ctx.upstream_results.get("counterfactual_analysis")
        scenarios: list[dict[str, Any]] = []
        if cf_result and cf_result.output:
            scenarios = cf_result.output.get("scenarios", [])

        if not root_causes:
            return self._success(
                output={"recommendations": []},
                message="No root causes identified; no recommendations generated.",
                confidence=0.90,
            )

        recommendations: list[dict[str, Any]] = []

        # Generate a recommendation for each distinct root cause.
        for rc in root_causes:
            category = rc.get("category", "unknown")
            rec = self._recommendation_for_category(category)
            recommendations.append(rec)

        # Enhance recommendations with counterfactual insights.
        self._enrich_with_counterfactuals(recommendations, scenarios)

        # De-duplicate by type (keep highest priority).
        recommendations = self._deduplicate(recommendations)

        return self._success(
            output={"recommendations": recommendations},
            message=(
                f"Generated {len(recommendations)} recommendation(s). "
                "Human review required."
            ),
            confidence=0.60,
        )

    # --- Helpers ---

    @staticmethod
    def _recommendation_for_category(category: str) -> dict[str, Any]:
        """Look up the canned recommendation for a root-cause category."""
        template = _CATEGORY_RECOMMENDATIONS.get(
            category,
            _CATEGORY_RECOMMENDATIONS["unknown"],
        )
        return dict(template)  # shallow copy

    @staticmethod
    def _enrich_with_counterfactuals(
        recommendations: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
    ) -> None:
        """Add counterfactual evidence to matching recommendations."""
        # Count how many scenarios suggest high improvement.
        high_improvement_names: set[str] = set()
        for sc in scenarios:
            if sc.get("likely_improvement") == "high":
                high_improvement_names.add(sc.get("name", ""))

        for rec in recommendations:
            if rec["type"] == REC_SIZING and "half_size" in high_improvement_names:
                rec["counterfactual_support"] = (
                    "Counterfactual confirms: halving size would have "
                    "materially reduced losses."
                )
            if (
                rec["type"] == REC_EXECUTION
                and "limit_instead_of_market" in high_improvement_names
            ):
                rec["counterfactual_support"] = (
                    "Counterfactual confirms: limit orders would have "
                    "avoided slippage."
                )
            if "skip_trade" in high_improvement_names:
                rec.setdefault("counterfactual_support", "")
                if rec["counterfactual_support"]:
                    rec["counterfactual_support"] += " "
                rec["counterfactual_support"] += (
                    "Skipping the trade was the highest-improvement scenario."
                )

    @staticmethod
    def _deduplicate(
        recommendations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep one recommendation per type, preferring higher priority."""
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        seen: dict[str, dict[str, Any]] = {}
        for rec in recommendations:
            rec_type = rec["type"]
            if rec_type not in seen:
                seen[rec_type] = rec
            else:
                existing_rank = priority_rank.get(
                    seen[rec_type].get("priority", "low"), 3
                )
                new_rank = priority_rank.get(rec.get("priority", "low"), 3)
                if new_rank < existing_rank:
                    seen[rec_type] = rec
        return list(seen.values())

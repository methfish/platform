"""
Lesson Extraction Skill - Converts incidents into reusable lessons.

Distils specific incidents and their analysis into generalised,
reusable lessons that can inform future trading decisions.
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

# Lesson templates keyed by root-cause category.
_LESSON_TEMPLATES: dict[str, dict[str, str]] = {
    "exchange": {
        "title": "Exchange Reliability Awareness",
        "category": "infrastructure",
        "description": (
            "Exchange errors can occur during periods of high load or "
            "network instability. Orders should be retried with back-off "
            "and fallback routing should be considered."
        ),
        "rule": (
            "Implement exponential back-off on exchange errors and add "
            "health-check gating before order submission."
        ),
        "watchout": (
            "Repeated exchange errors may indicate a systemic outage - "
            "halt trading until connectivity is confirmed."
        ),
    },
    "risk_control": {
        "title": "Risk Limit Calibration",
        "category": "risk_management",
        "description": (
            "Risk controls rejected or flagged an order. This may indicate "
            "that limits are too tight for the current market regime, or "
            "that the position was genuinely too risky."
        ),
        "rule": (
            "Periodically recalibrate risk thresholds against recent market "
            "conditions and portfolio size."
        ),
        "watchout": (
            "Do not relax risk limits reactively after a single incident; "
            "verify with multiple data points."
        ),
    },
    "sizing": {
        "title": "Position Sizing Discipline",
        "category": "risk_management",
        "description": (
            "Oversized positions amplify losses and increase slippage. "
            "Sizing should be proportional to volatility and liquidity."
        ),
        "rule": (
            "Use volatility-adjusted sizing and never exceed the maximum "
            "position limit regardless of signal strength."
        ),
        "watchout": (
            "High-conviction signals do not justify ignoring sizing rules."
        ),
    },
    "execution": {
        "title": "Execution Quality Monitoring",
        "category": "execution",
        "description": (
            "Execution slippage or poor fill quality was observed. "
            "Consider order type selection and timing."
        ),
        "rule": (
            "Prefer limit orders for non-urgent entries and track "
            "slippage as a first-class metric."
        ),
        "watchout": (
            "Market orders during low liquidity or high volatility "
            "periods will incur above-average slippage."
        ),
    },
    "market": {
        "title": "Market Risk Acceptance",
        "category": "market",
        "description": (
            "Adverse market movement caused the loss. This is inherent "
            "to trading and may not be avoidable."
        ),
        "rule": (
            "Ensure stop-losses are in place and portfolio diversification "
            "limits single-asset exposure."
        ),
        "watchout": (
            "Consecutive market losses may indicate a regime change - "
            "check market regime classification."
        ),
    },
    "model": {
        "title": "Model Signal Review",
        "category": "model",
        "description": (
            "The trading model produced a signal that led to a losing "
            "trade. Model accuracy may be degrading."
        ),
        "rule": (
            "Track model hit rate and Sharpe over rolling windows. "
            "Disable signals when performance drops below threshold."
        ),
        "watchout": (
            "Models trained on historical data may not capture "
            "structural regime shifts."
        ),
    },
    "data": {
        "title": "Data Integrity Vigilance",
        "category": "data",
        "description": (
            "Stale, missing, or incorrect data contributed to the incident. "
            "Data quality is foundational to correct decisions."
        ),
        "rule": (
            "Gate all trading decisions behind data freshness checks. "
            "Implement fallback data sources."
        ),
        "watchout": (
            "NaN or zero values in pricing data can cascade through "
            "the entire decision pipeline."
        ),
    },
    "system_bug": {
        "title": "Software Defect Prevention",
        "category": "engineering",
        "description": (
            "A software bug caused the incident. This is fully preventable "
            "with proper testing and error handling."
        ),
        "rule": (
            "Add regression tests for every production incident. "
            "Implement defensive coding with assertion checks."
        ),
        "watchout": (
            "Silent failures are more dangerous than loud ones - "
            "prefer fail-fast over fail-silent."
        ),
    },
    "unknown": {
        "title": "Unknown Failure Investigation",
        "category": "investigation",
        "description": (
            "The root cause could not be automatically determined. "
            "Manual investigation is required."
        ),
        "rule": (
            "When automated analysis is inconclusive, escalate to a "
            "human reviewer with full context."
        ),
        "watchout": (
            "Unknown causes that recur may indicate a gap in the "
            "monitoring or classification system itself."
        ),
    },
}


class LessonExtractionSkill(BaseSkill):
    """Hybrid skill that extracts reusable lessons from incident analysis."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "lesson_extraction"

    @property
    def name(self) -> str:
        return "Lesson Extraction"

    @property
    def description(self) -> str:
        return (
            "Converts specific incidents into reusable lessons with "
            "rules and watchouts."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.HYBRID

    @property
    def required_inputs(self) -> list[str]:
        return []

    @property
    def prerequisites(self) -> list[str]:
        return ["recommendation_generation"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Pull root causes for lesson templates.
        rc_result = ctx.upstream_results.get("root_cause_classification")
        root_causes: list[dict[str, Any]] = []
        if rc_result and rc_result.output:
            root_causes = rc_result.output.get("root_causes", [])

        # Pull recommendations for enrichment.
        rec_result = ctx.upstream_results.get("recommendation_generation")
        recommendations: list[dict[str, Any]] = []
        if rec_result and rec_result.output:
            recommendations = rec_result.output.get("recommendations", [])

        if not root_causes:
            return self._success(
                output={"lessons": []},
                message="No root causes identified; no lessons to extract.",
                confidence=0.90,
            )

        lessons: list[dict[str, Any]] = []
        seen_categories: set[str] = set()

        for rc in root_causes:
            category = rc.get("category", "unknown")
            if category in seen_categories:
                continue
            seen_categories.add(category)

            template = _LESSON_TEMPLATES.get(
                category, _LESSON_TEMPLATES["unknown"]
            )
            lesson: dict[str, Any] = dict(template)

            # Enrich with specific evidence from root cause.
            evidence = rc.get("evidence", "")
            if evidence:
                lesson["specific_evidence"] = evidence

            # Enrich with recommendation context if available.
            for rec in recommendations:
                if rec.get("type", "").endswith("_change"):
                    lesson.setdefault("linked_recommendation", rec.get(
                        "description", ""
                    ))
                    break

            lessons.append(lesson)

        return self._success(
            output={"lessons": lessons},
            message=f"Extracted {len(lessons)} lesson(s) from incident analysis.",
            confidence=0.75,
        )

"""
Report Writing Skill - Compiles a structured post-mortem report.

Aggregates outputs from all upstream skills into a single cohesive
report suitable for human review and archival.
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


class ReportWritingSkill(BaseSkill):
    """Model-assisted post-mortem report compiler requiring human review."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "report_writing"

    @property
    def name(self) -> str:
        return "Report Writing"

    @property
    def description(self) -> str:
        return (
            "Generates a structured post-mortem report combining all "
            "upstream analysis outputs."
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
        return ["lesson_extraction"]

    @property
    def requires_human_review(self) -> bool:
        return True

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Collect all upstream outputs.
        incident_output = self._get_upstream_output(ctx, "incident_detection")
        timeline_output = self._get_upstream_output(ctx, "timeline_reconstruction")
        rc_output = self._get_upstream_output(ctx, "root_cause_classification")
        cf_output = self._get_upstream_output(ctx, "counterfactual_analysis")
        rec_output = self._get_upstream_output(ctx, "recommendation_generation")
        lesson_output = self._get_upstream_output(ctx, "lesson_extraction")

        # Build summary.
        incidents = incident_output.get("incidents", [])
        root_causes = rc_output.get("root_causes", [])
        recommendations = rec_output.get("recommendations", [])
        lessons = lesson_output.get("lessons", [])
        scenarios = cf_output.get("scenarios", [])
        total_incidents = incident_output.get("total_count", len(incidents))

        # Determine if incidents were preventable.
        preventable = self._assess_preventability(root_causes, scenarios)

        # Determine if human review is truly needed (always true for this
        # skill, but the flag in the report can be used by downstream consumers).
        human_review_needed = True

        # Build summary text.
        summary = self._build_summary(
            total_incidents=total_incidents,
            root_causes=root_causes,
            recommendations=recommendations,
            preventable=preventable,
            duration_span=timeline_output.get("duration_span", ""),
        )

        return self._success(
            output={
                "summary": summary,
                "root_causes": root_causes,
                "recommendations": recommendations,
                "lessons": lessons,
                "preventable": preventable,
                "human_review_needed": human_review_needed,
                "incident_count": total_incidents,
                "timeline_event_count": timeline_output.get("event_count", 0),
                "scenario_count": len(scenarios),
            },
            message="Post-mortem report compiled. Human review required.",
            confidence=0.55,
        )

    # --- Helpers ---

    @staticmethod
    def _get_upstream_output(
        ctx: SkillContext, skill_id: str
    ) -> dict[str, Any]:
        """Safely retrieve output dict from an upstream skill result."""
        result = ctx.upstream_results.get(skill_id)
        if result and result.output:
            return result.output
        return {}

    @staticmethod
    def _assess_preventability(
        root_causes: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
    ) -> bool:
        """
        Determine if the incidents were likely preventable.

        An incident is considered preventable if:
        - The root cause is not purely 'market' or 'unknown'.
        - At least one counterfactual scenario shows 'high' improvement.
        """
        non_market_causes = [
            rc for rc in root_causes
            if rc.get("category") not in ("market", "unknown")
        ]
        high_improvement_scenarios = [
            sc for sc in scenarios
            if sc.get("likely_improvement") == "high"
        ]
        return bool(non_market_causes) or bool(high_improvement_scenarios)

    @staticmethod
    def _build_summary(
        total_incidents: int,
        root_causes: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        preventable: bool,
        duration_span: str,
    ) -> str:
        """Build a human-readable summary string."""
        parts: list[str] = []

        parts.append(
            f"Post-mortem analysis identified {total_incidents} incident(s)."
        )

        if duration_span:
            parts.append(f"Timeline span: {duration_span}.")

        if root_causes:
            categories = [rc.get("category", "unknown") for rc in root_causes]
            parts.append(
                f"Root cause(s): {', '.join(categories)}."
            )

        parts.append(
            f"Preventable: {'Yes' if preventable else 'No/Unclear'}."
        )

        if recommendations:
            rec_types = [r.get("type", "unknown") for r in recommendations]
            parts.append(
                f"Recommendations ({len(recommendations)}): "
                f"{', '.join(rec_types)}."
            )

        return " ".join(parts)

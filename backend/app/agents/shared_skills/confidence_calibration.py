"""
Confidence Calibration Skill - Shared between agents.

Aggregates confidence values from all upstream skill results and
produces a calibrated overall confidence score.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillStatus,
)

logger = logging.getLogger(__name__)

# Adjustment factors.
_FAILURE_PENALTY = 0.15          # Per-failed-skill penalty.
_LOW_CONFIDENCE_THRESHOLD = 0.5  # Individual skills below this are flagged.
_MIN_CALIBRATED = 0.05           # Floor for calibrated confidence.
_MAX_CALIBRATED = 0.99           # Ceiling for calibrated confidence.


class ConfidenceCalibrationSkill(BaseSkill):
    """Deterministic confidence aggregator across upstream results."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "confidence_calibration"

    @property
    def name(self) -> str:
        return "Confidence Calibration"

    @property
    def description(self) -> str:
        return (
            "Calibrates overall confidence by aggregating upstream skill "
            "confidences and applying adjustment factors."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def required_inputs(self) -> list[str]:
        return []

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        upstream = ctx.upstream_results
        if not upstream:
            return self._success(
                output={
                    "calibrated_confidence": 0.50,
                    "contributing_skills": [],
                    "adjustment_factors": {"reason": "no_upstream_results"},
                },
                message="No upstream results; returning default confidence.",
                confidence=0.50,
            )

        contributing_skills: list[dict[str, Any]] = []
        confidences: list[float] = []
        failed_count = 0
        low_confidence_count = 0

        for skill_id, result in upstream.items():
            # Skip self to avoid recursion artifacts.
            if skill_id == self.skill_id:
                continue

            entry: dict[str, Any] = {
                "skill_id": skill_id,
                "status": result.status.value,
                "confidence": result.confidence,
            }
            contributing_skills.append(entry)

            if result.confidence is not None:
                confidences.append(result.confidence)
                if result.confidence < _LOW_CONFIDENCE_THRESHOLD:
                    low_confidence_count += 1

            if result.status in (
                SkillStatus.FAILURE,
                SkillStatus.ERROR,
                SkillStatus.TIMEOUT,
            ):
                failed_count += 1

        # Compute raw average confidence.
        if confidences:
            raw_avg = sum(confidences) / len(confidences)
        else:
            raw_avg = 0.50

        # Apply adjustments.
        adjustment = 0.0

        # Penalty for failed skills.
        failure_penalty = failed_count * _FAILURE_PENALTY
        adjustment -= failure_penalty

        # Penalty for many low-confidence skills.
        if len(confidences) > 0:
            low_ratio = low_confidence_count / len(confidences)
            if low_ratio > 0.5:
                adjustment -= 0.10

        calibrated = raw_avg + adjustment
        calibrated = max(_MIN_CALIBRATED, min(_MAX_CALIBRATED, calibrated))

        adjustment_factors: dict[str, Any] = {
            "raw_average": round(raw_avg, 4),
            "failure_penalty": round(failure_penalty, 4),
            "failed_skill_count": failed_count,
            "low_confidence_skill_count": low_confidence_count,
            "total_upstream_skills": len(contributing_skills),
            "total_with_confidence": len(confidences),
            "net_adjustment": round(adjustment, 4),
        }

        return self._success(
            output={
                "calibrated_confidence": round(calibrated, 4),
                "contributing_skills": contributing_skills,
                "adjustment_factors": adjustment_factors,
            },
            message=(
                f"Calibrated confidence: {calibrated:.2f} "
                f"(raw avg={raw_avg:.2f}, adjustment={adjustment:+.2f})."
            ),
            confidence=round(calibrated, 4),
        )

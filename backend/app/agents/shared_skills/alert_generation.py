"""
Alert Generation Skill - Shared between agents.

Generates alert messages based on upstream failures, warnings,
or notable outcomes discovered during the pipeline execution.
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

# Severity constants.
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"
SEVERITY_INFO = "info"


class AlertGenerationSkill(BaseSkill):
    """Deterministic alert generator from upstream pipeline results."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "alert_generation"

    @property
    def name(self) -> str:
        return "Alert Generation"

    @property
    def description(self) -> str:
        return (
            "Generates alert messages based on upstream failures, "
            "warnings, or notable outcomes."
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

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        alerts: list[dict[str, Any]] = []

        # Scan all upstream results for notable conditions.
        for skill_id, result in ctx.upstream_results.items():
            # Skip self.
            if skill_id == self.skill_id:
                continue

            # Alert on failed / errored / timed-out skills.
            if result.status == SkillStatus.ERROR:
                alerts.append({
                    "severity": SEVERITY_CRITICAL,
                    "message": (
                        f"Skill '{skill_id}' raised an error: "
                        f"{result.message}"
                    ),
                    "source_skill": skill_id,
                })
            elif result.status == SkillStatus.TIMEOUT:
                alerts.append({
                    "severity": SEVERITY_HIGH,
                    "message": (
                        f"Skill '{skill_id}' timed out: {result.message}"
                    ),
                    "source_skill": skill_id,
                })
            elif result.status == SkillStatus.FAILURE:
                alerts.append({
                    "severity": SEVERITY_HIGH,
                    "message": (
                        f"Skill '{skill_id}' failed: {result.message}"
                    ),
                    "source_skill": skill_id,
                })

            # Alert on low confidence.
            if (
                result.confidence is not None
                and result.confidence < 0.4
                and result.status == SkillStatus.SUCCESS
            ):
                alerts.append({
                    "severity": SEVERITY_MEDIUM,
                    "message": (
                        f"Skill '{skill_id}' succeeded but with low "
                        f"confidence ({result.confidence:.2f})."
                    ),
                    "source_skill": skill_id,
                })

            # Alert on human-review-required outputs.
            if result.requires_human_review and result.status == SkillStatus.SUCCESS:
                alerts.append({
                    "severity": SEVERITY_INFO,
                    "message": (
                        f"Skill '{skill_id}' output requires human review."
                    ),
                    "source_skill": skill_id,
                })

        # Check for specific high-impact outputs from known skills.
        alerts.extend(self._check_incident_alerts(ctx))
        alerts.extend(self._check_exchange_alerts(ctx))

        # De-duplicate by (severity, source_skill, message).
        alerts = self._deduplicate(alerts)

        # Sort by severity.
        severity_order = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 1,
            SEVERITY_MEDIUM: 2,
            SEVERITY_LOW: 3,
            SEVERITY_INFO: 4,
        }
        alerts.sort(key=lambda a: severity_order.get(a["severity"], 5))

        return self._success(
            output={
                "alerts": alerts,
                "alert_count": len(alerts),
            },
            message=f"Generated {len(alerts)} alert(s).",
            confidence=0.90,
        )

    # --- Domain-specific alert checks ---

    @staticmethod
    def _check_incident_alerts(ctx: SkillContext) -> list[dict[str, Any]]:
        """Generate alerts from incident detection output."""
        alerts: list[dict[str, Any]] = []
        result = ctx.upstream_results.get("incident_detection")
        if not result or not result.output:
            return alerts

        total = result.output.get("total_count", 0)
        if total > 0:
            incidents = result.output.get("incidents", [])
            high_priority = [
                i for i in incidents
                if i.get("priority_score", 0) >= 0.8
            ]
            if high_priority:
                alerts.append({
                    "severity": SEVERITY_HIGH,
                    "message": (
                        f"{len(high_priority)} high-priority incident(s) "
                        f"detected out of {total} total."
                    ),
                    "source_skill": "incident_detection",
                })
            elif total >= 3:
                alerts.append({
                    "severity": SEVERITY_MEDIUM,
                    "message": (
                        f"{total} incidents detected in order history."
                    ),
                    "source_skill": "incident_detection",
                })

        return alerts

    @staticmethod
    def _check_exchange_alerts(ctx: SkillContext) -> list[dict[str, Any]]:
        """Generate alerts from exchange health output."""
        alerts: list[dict[str, Any]] = []
        result = ctx.upstream_results.get("exchange_health")
        if not result or not result.output:
            return alerts

        if not result.output.get("is_healthy", True):
            status = result.output.get("exchange_status", "UNKNOWN")
            latency = result.output.get("latency_ms", 0)
            degraded = result.output.get("degraded_services", [])
            parts = [f"Exchange is {status}"]
            if latency:
                parts.append(f"latency={latency}ms")
            if degraded:
                parts.append(f"degraded={', '.join(degraded)}")
            alerts.append({
                "severity": SEVERITY_HIGH,
                "message": "; ".join(parts) + ".",
                "source_skill": "exchange_health",
            })

        return alerts

    @staticmethod
    def _deduplicate(
        alerts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove duplicate alerts based on (severity, source, message)."""
        seen: set[tuple[str, str, str]] = set()
        unique: list[dict[str, Any]] = []
        for alert in alerts:
            key = (
                alert.get("severity", ""),
                alert.get("source_skill", ""),
                alert.get("message", ""),
            )
            if key not in seen:
                seen.add(key)
                unique.append(alert)
        return unique

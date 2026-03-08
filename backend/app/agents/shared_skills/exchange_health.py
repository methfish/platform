"""
Exchange Health Skill - Shared between agents.

Checks exchange connectivity status from the risk_state dictionary.
Reports overall health, latency, and any degraded services.
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

# Latency thresholds (milliseconds).
_LATENCY_HEALTHY_MS = 500
_LATENCY_DEGRADED_MS = 2000


class ExchangeHealthSkill(BaseSkill):
    """Deterministic exchange health checker."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "exchange_health"

    @property
    def name(self) -> str:
        return "Exchange Health Check"

    @property
    def description(self) -> str:
        return (
            "Checks exchange connectivity status from risk_state. "
            "Reports health, latency, and degraded services."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def required_inputs(self) -> list[str]:
        return ["risk_state"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        rs = ctx.risk_state
        if not rs:
            return self._failure("risk_state is empty.")

        # Extract exchange health data.  The risk_state may store this
        # under various keys depending on upstream systems.
        exchange_data = (
            rs.get("exchange_health")
            or rs.get("exchange_status")
            or rs.get("exchange")
            or {}
        )

        # If exchange_data is a simple status string, wrap it.
        if isinstance(exchange_data, str):
            exchange_data = {"status": exchange_data}

        raw_status = str(exchange_data.get("status", "unknown")).upper()
        latency_ms = self._extract_latency(exchange_data, rs)
        degraded_services = self._extract_degraded_services(exchange_data, rs)

        # Determine canonical status.
        exchange_status, is_healthy = self._determine_status(
            raw_status, latency_ms, degraded_services
        )

        confidence = 0.90 if raw_status != "UNKNOWN" else 0.40

        return self._success(
            output={
                "exchange_status": exchange_status,
                "latency_ms": latency_ms,
                "is_healthy": is_healthy,
                "degraded_services": degraded_services,
            },
            message=(
                f"Exchange status: {exchange_status} "
                f"(latency={latency_ms}ms, healthy={is_healthy})."
            ),
            confidence=confidence,
        )

    # --- Helpers ---

    @staticmethod
    def _extract_latency(
        exchange_data: dict[str, Any],
        risk_state: dict[str, Any],
    ) -> int:
        """Extract latency in ms from available data."""
        for source in (exchange_data, risk_state):
            for key in ("latency_ms", "latency", "ping_ms", "response_time_ms"):
                val = source.get(key)
                if val is not None:
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        continue
        return 0

    @staticmethod
    def _extract_degraded_services(
        exchange_data: dict[str, Any],
        risk_state: dict[str, Any],
    ) -> list[str]:
        """Extract list of degraded service names."""
        for source in (exchange_data, risk_state):
            for key in ("degraded_services", "degraded", "warnings"):
                val = source.get(key)
                if isinstance(val, list):
                    return [str(s) for s in val]
        return []

    @staticmethod
    def _determine_status(
        raw_status: str,
        latency_ms: int,
        degraded_services: list[str],
    ) -> tuple[str, bool]:
        """
        Determine canonical status and health boolean.

        Returns (status_string, is_healthy).
        """
        # Explicit unhealthy statuses.
        if raw_status in ("DOWN", "OFFLINE", "ERROR", "UNAVAILABLE"):
            return "DOWN", False

        # Check for degraded state.
        if raw_status in ("DEGRADED", "PARTIAL"):
            return "DEGRADED", False

        if degraded_services:
            return "DEGRADED", False

        if latency_ms > _LATENCY_DEGRADED_MS:
            return "DEGRADED", False

        # Healthy but slow.
        if latency_ms > _LATENCY_HEALTHY_MS:
            return "SLOW", True

        # Explicit healthy.
        if raw_status in ("OK", "HEALTHY", "UP", "ONLINE", "CONNECTED"):
            return "HEALTHY", True

        # Unknown but no negative signals.
        if raw_status == "UNKNOWN":
            return "UNKNOWN", False

        # Default: treat as healthy.
        return "HEALTHY", True

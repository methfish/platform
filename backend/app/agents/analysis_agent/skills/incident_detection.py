"""
Incident Detection Skill - Scans order history for trading incidents.

Identifies rejected orders, failed orders, exchange rejections,
large losses, and slippage breaches from the order history.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)

logger = logging.getLogger(__name__)

# Incident type constants.
INCIDENT_REJECTED = "rejected_order"
INCIDENT_FAILED = "failed_order"
INCIDENT_EXCHANGE_REJECTION = "exchange_rejection"
INCIDENT_LARGE_LOSS = "large_loss"
INCIDENT_SLIPPAGE_BREACH = "slippage_breach"

# Thresholds for incident detection.
_LARGE_LOSS_THRESHOLD_PCT = Decimal("2.0")  # > 2 % loss on a single order
_SLIPPAGE_THRESHOLD_PCT = Decimal("0.5")    # > 0.5 % slippage

# Priority weights per incident type (higher = more urgent).
_PRIORITY_WEIGHTS: dict[str, float] = {
    INCIDENT_REJECTED: 0.4,
    INCIDENT_FAILED: 0.6,
    INCIDENT_EXCHANGE_REJECTION: 0.7,
    INCIDENT_LARGE_LOSS: 0.9,
    INCIDENT_SLIPPAGE_BREACH: 0.5,
}


class IncidentDetectionSkill(BaseSkill):
    """Deterministic scan of order history to surface trading incidents."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "incident_detection"

    @property
    def name(self) -> str:
        return "Incident Detection"

    @property
    def description(self) -> str:
        return (
            "Scans order history for incidents: rejected orders, failed orders, "
            "exchange rejections, large losses, and slippage breaches."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def required_inputs(self) -> list[str]:
        return ["order_history"]

    # --- Overridden optional properties ---

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.HIGH

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        order_history: list[dict[str, Any]] = ctx.order_history
        if not order_history:
            return self._skip("Order history is empty; nothing to scan.")

        incidents: list[dict[str, Any]] = []

        for order in order_history:
            order_id = order.get("order_id", "unknown")
            status = str(order.get("status", "")).upper()
            reason = order.get("reason", "")
            timestamp = order.get("timestamp", "")

            # Rejected orders
            if status == "REJECTED":
                incidents.append(
                    self._build_incident(
                        INCIDENT_REJECTED, order_id, reason, timestamp
                    )
                )

            # Failed orders
            if status == "FAILED":
                incidents.append(
                    self._build_incident(
                        INCIDENT_FAILED, order_id, reason, timestamp
                    )
                )

            # Exchange rejection (may overlap with REJECTED but uses error_code)
            error_code = order.get("error_code", "")
            if error_code:
                incidents.append(
                    self._build_incident(
                        INCIDENT_EXCHANGE_REJECTION,
                        order_id,
                        f"Exchange error: {error_code} - {reason}",
                        timestamp,
                    )
                )

            # Large loss detection
            pnl = order.get("realized_pnl")
            entry_value = order.get("entry_value") or order.get("notional")
            if pnl is not None and entry_value:
                try:
                    pnl_dec = Decimal(str(pnl))
                    entry_dec = Decimal(str(entry_value))
                    if entry_dec > 0:
                        loss_pct = (pnl_dec / entry_dec) * Decimal("100")
                        if loss_pct < -_LARGE_LOSS_THRESHOLD_PCT:
                            incidents.append(
                                self._build_incident(
                                    INCIDENT_LARGE_LOSS,
                                    order_id,
                                    f"Loss of {loss_pct:.2f}% on order",
                                    timestamp,
                                )
                            )
                except (ArithmeticError, ValueError):
                    logger.debug(
                        "Could not compute PnL for order %s", order_id
                    )

            # Slippage breach
            expected_price = order.get("expected_price")
            filled_price = order.get("filled_price")
            if expected_price is not None and filled_price is not None:
                try:
                    expected_dec = Decimal(str(expected_price))
                    filled_dec = Decimal(str(filled_price))
                    if expected_dec > 0:
                        slippage_pct = abs(
                            (filled_dec - expected_dec) / expected_dec
                        ) * Decimal("100")
                        if slippage_pct > _SLIPPAGE_THRESHOLD_PCT:
                            incidents.append(
                                self._build_incident(
                                    INCIDENT_SLIPPAGE_BREACH,
                                    order_id,
                                    f"Slippage of {slippage_pct:.2f}% "
                                    f"(expected={expected_dec}, filled={filled_dec})",
                                    timestamp,
                                )
                            )
                except (ArithmeticError, ValueError):
                    logger.debug(
                        "Could not compute slippage for order %s", order_id
                    )

        # Compute priority score for each incident.
        for incident in incidents:
            incident["priority_score"] = _PRIORITY_WEIGHTS.get(
                incident["type"], 0.3
            )

        # Sort by priority descending.
        incidents.sort(key=lambda i: i["priority_score"], reverse=True)

        if not incidents:
            return self._success(
                output={
                    "incidents": [],
                    "total_count": 0,
                },
                message="No incidents detected in order history.",
                confidence=0.95,
            )

        return self._success(
            output={
                "incidents": incidents,
                "total_count": len(incidents),
            },
            message=f"Detected {len(incidents)} incident(s) in order history.",
            confidence=0.90,
        )

    # --- Helpers ---

    @staticmethod
    def _build_incident(
        incident_type: str,
        order_id: str,
        reason: str,
        timestamp: str,
    ) -> dict[str, Any]:
        return {
            "type": incident_type,
            "order_id": order_id,
            "reason": reason,
            "timestamp": timestamp,
            "priority_score": 0.0,  # filled in later
        }

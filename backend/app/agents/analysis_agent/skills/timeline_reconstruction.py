"""
Timeline Reconstruction Skill - Builds an ordered timeline of events.

Combines order history entries and detected incidents into a single
chronological timeline for downstream analysis.
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


class TimelineReconstructionSkill(BaseSkill):
    """Deterministic construction of an ordered event timeline."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "timeline_reconstruction"

    @property
    def name(self) -> str:
        return "Timeline Reconstruction"

    @property
    def description(self) -> str:
        return (
            "Builds an ordered timeline of events from order history "
            "and upstream incident data."
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

    @property
    def prerequisites(self) -> list[str]:
        return ["incident_detection"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        order_history: list[dict[str, Any]] = ctx.order_history
        if not order_history:
            return self._skip("Order history is empty; cannot build timeline.")

        # Gather incident data from the upstream skill.
        incident_result = ctx.upstream_results.get("incident_detection")
        incident_list: list[dict[str, Any]] = []
        if incident_result and incident_result.output:
            incident_list = incident_result.output.get("incidents", [])

        # Build a set of incident order_ids for cross-referencing.
        incident_order_ids: set[str] = {
            inc.get("order_id", "") for inc in incident_list
        }

        timeline: list[dict[str, Any]] = []

        # Add order events.
        for order in order_history:
            ts = order.get("timestamp", "")
            order_id = order.get("order_id", "unknown")
            status = str(order.get("status", "")).upper()
            side = order.get("side", "")
            symbol = order.get("symbol", ctx.symbol)
            qty = order.get("quantity", "")

            event_type = "order_" + status.lower() if status else "order_event"

            details: dict[str, Any] = {
                "order_id": order_id,
                "status": status,
                "side": side,
                "symbol": symbol,
                "quantity": str(qty),
                "is_incident": order_id in incident_order_ids,
            }

            # Include fill information when available.
            if order.get("filled_price"):
                details["filled_price"] = str(order["filled_price"])
            if order.get("filled_quantity"):
                details["filled_quantity"] = str(order["filled_quantity"])

            timeline.append({
                "timestamp": ts,
                "event_type": event_type,
                "details": details,
            })

        # Add incident events that may not directly map to a single order.
        for incident in incident_list:
            ts = incident.get("timestamp", "")
            timeline.append({
                "timestamp": ts,
                "event_type": f"incident_{incident.get('type', 'unknown')}",
                "details": {
                    "incident_type": incident.get("type", ""),
                    "order_id": incident.get("order_id", ""),
                    "reason": incident.get("reason", ""),
                    "priority_score": incident.get("priority_score", 0.0),
                },
            })

        # Sort chronologically (best-effort string sort; ISO-8601 friendly).
        timeline.sort(key=lambda e: e.get("timestamp", ""))

        # Compute duration span.
        timestamps = [e["timestamp"] for e in timeline if e.get("timestamp")]
        duration_span = ""
        if len(timestamps) >= 2:
            duration_span = f"{timestamps[0]} -> {timestamps[-1]}"

        return self._success(
            output={
                "timeline": timeline,
                "event_count": len(timeline),
                "duration_span": duration_span,
            },
            message=f"Reconstructed timeline with {len(timeline)} events.",
            confidence=0.85,
        )

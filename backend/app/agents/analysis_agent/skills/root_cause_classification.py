"""
Root Cause Classification Skill - Classifies root causes of incidents.

Uses deterministic rules first (e.g. exchange error codes map to
"exchange", risk rejection maps to "risk_control"). Falls back to
heuristic matching or "unknown" when no rule triggers.
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

# Canonical root cause categories.
CATEGORY_MARKET = "market"
CATEGORY_MODEL = "model"
CATEGORY_SIZING = "sizing"
CATEGORY_EXECUTION = "execution"
CATEGORY_EXCHANGE = "exchange"
CATEGORY_DATA = "data"
CATEGORY_RISK_CONTROL = "risk_control"
CATEGORY_SYSTEM_BUG = "system_bug"
CATEGORY_UNKNOWN = "unknown"

# Keyword-based heuristic mapping for reason strings.
_KEYWORD_MAP: dict[str, str] = {
    "exchange error": CATEGORY_EXCHANGE,
    "exchange_error": CATEGORY_EXCHANGE,
    "connection": CATEGORY_EXCHANGE,
    "timeout": CATEGORY_EXCHANGE,
    "rate limit": CATEGORY_EXCHANGE,
    "rate_limit": CATEGORY_EXCHANGE,
    "insufficient balance": CATEGORY_SIZING,
    "insufficient_balance": CATEGORY_SIZING,
    "position too large": CATEGORY_SIZING,
    "position_too_large": CATEGORY_SIZING,
    "max position": CATEGORY_SIZING,
    "risk": CATEGORY_RISK_CONTROL,
    "risk_check": CATEGORY_RISK_CONTROL,
    "risk limit": CATEGORY_RISK_CONTROL,
    "drawdown": CATEGORY_RISK_CONTROL,
    "circuit breaker": CATEGORY_RISK_CONTROL,
    "circuit_breaker": CATEGORY_RISK_CONTROL,
    "slippage": CATEGORY_EXECUTION,
    "fill": CATEGORY_EXECUTION,
    "partial fill": CATEGORY_EXECUTION,
    "market impact": CATEGORY_MARKET,
    "volatility": CATEGORY_MARKET,
    "gap": CATEGORY_MARKET,
    "stale": CATEGORY_DATA,
    "missing data": CATEGORY_DATA,
    "data feed": CATEGORY_DATA,
    "nan": CATEGORY_DATA,
    "model": CATEGORY_MODEL,
    "signal": CATEGORY_MODEL,
    "prediction": CATEGORY_MODEL,
    "assertion": CATEGORY_SYSTEM_BUG,
    "exception": CATEGORY_SYSTEM_BUG,
    "traceback": CATEGORY_SYSTEM_BUG,
    "null pointer": CATEGORY_SYSTEM_BUG,
    "key error": CATEGORY_SYSTEM_BUG,
}


class RootCauseClassificationSkill(BaseSkill):
    """Hybrid root-cause classifier using deterministic rules and heuristics."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "root_cause_classification"

    @property
    def name(self) -> str:
        return "Root Cause Classification"

    @property
    def description(self) -> str:
        return (
            "Classifies root causes of incidents into categories: market, "
            "model, sizing, execution, exchange, data, risk_control, "
            "system_bug, or unknown."
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
        return ["timeline_reconstruction"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Pull incident list from upstream.
        incident_result = ctx.upstream_results.get("incident_detection")
        if not incident_result or not incident_result.output:
            return self._skip("No incident data available for classification.")

        incidents: list[dict[str, Any]] = incident_result.output.get(
            "incidents", []
        )
        if not incidents:
            return self._success(
                output={"root_causes": []},
                message="No incidents to classify.",
                confidence=0.95,
            )

        root_causes: list[dict[str, Any]] = []
        seen_categories: set[str] = set()

        for incident in incidents:
            category, confidence, evidence = self._classify_incident(incident)

            # Aggregate: only report distinct categories, pick highest confidence.
            if category not in seen_categories:
                root_causes.append({
                    "category": category,
                    "confidence": confidence,
                    "evidence": evidence,
                })
                seen_categories.add(category)
            else:
                # Update confidence if this evidence is stronger.
                for rc in root_causes:
                    if rc["category"] == category and confidence > rc["confidence"]:
                        rc["confidence"] = confidence
                        rc["evidence"] = evidence

        # Sort by confidence descending.
        root_causes.sort(key=lambda r: r["confidence"], reverse=True)

        return self._success(
            output={"root_causes": root_causes},
            message=f"Classified {len(root_causes)} root cause(s).",
            confidence=min(
                (rc["confidence"] for rc in root_causes), default=0.5
            ),
        )

    # --- Classification logic ---

    def _classify_incident(
        self, incident: dict[str, Any]
    ) -> tuple[str, float, str]:
        """
        Classify a single incident.

        Returns (category, confidence, evidence_string).
        """
        incident_type = incident.get("type", "")
        reason = str(incident.get("reason", "")).lower()

        # Rule 1: Exchange error codes -> EXCHANGE
        if incident_type == "exchange_rejection":
            return (
                CATEGORY_EXCHANGE,
                0.95,
                f"Exchange rejection detected: {incident.get('reason', '')}",
            )

        # Rule 2: Risk-related rejection reasons -> RISK_CONTROL
        if any(
            kw in reason
            for kw in ("risk", "drawdown", "circuit breaker", "circuit_breaker")
        ):
            return (
                CATEGORY_RISK_CONTROL,
                0.90,
                f"Risk control triggered: {incident.get('reason', '')}",
            )

        # Rule 3: Slippage breach -> EXECUTION
        if incident_type == "slippage_breach":
            return (
                CATEGORY_EXECUTION,
                0.85,
                f"Slippage breach: {incident.get('reason', '')}",
            )

        # Rule 4: Large loss -> heuristic on reason
        if incident_type == "large_loss":
            # Try keyword matching on the reason string.
            for keyword, category in _KEYWORD_MAP.items():
                if keyword in reason:
                    return (
                        category,
                        0.70,
                        f"Large loss with keyword match '{keyword}': "
                        f"{incident.get('reason', '')}",
                    )
            # Default large loss to market if no keyword matches.
            return (
                CATEGORY_MARKET,
                0.60,
                f"Large loss without specific cause: {incident.get('reason', '')}",
            )

        # Fallback: keyword-based heuristic across all incident reasons.
        for keyword, category in _KEYWORD_MAP.items():
            if keyword in reason:
                return (
                    category,
                    0.65,
                    f"Keyword match '{keyword}' in reason: "
                    f"{incident.get('reason', '')}",
                )

        # Last resort: unknown.
        return (
            CATEGORY_UNKNOWN,
            0.30,
            f"No matching rule for incident: {incident.get('reason', '')}",
        )

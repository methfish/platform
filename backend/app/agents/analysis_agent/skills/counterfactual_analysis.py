"""
Counterfactual Analysis Skill - Evaluates alternative scenarios.

For each incident, estimates what would have happened under different
conditions: smaller size, delayed entry, limit order instead of market,
or skipping the trade entirely.
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
)

logger = logging.getLogger(__name__)


class CounterfactualAnalysisSkill(BaseSkill):
    """Hybrid counterfactual scenario evaluator."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "counterfactual_analysis"

    @property
    def name(self) -> str:
        return "Counterfactual Analysis"

    @property
    def description(self) -> str:
        return (
            "Evaluates alternative scenarios: 50% size, 1-min delay, "
            "limit instead of market, and skip trade."
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
        return ["root_cause_classification"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        # Pull incident data from upstream.
        incident_result = ctx.upstream_results.get("incident_detection")
        if not incident_result or not incident_result.output:
            return self._skip("No incident data for counterfactual analysis.")

        incidents: list[dict[str, Any]] = incident_result.output.get(
            "incidents", []
        )
        if not incidents:
            return self._success(
                output={"scenarios": []},
                message="No incidents to evaluate counterfactuals for.",
                confidence=0.90,
            )

        # Pull root cause data for context.
        root_cause_result = ctx.upstream_results.get("root_cause_classification")
        root_causes: list[dict[str, Any]] = []
        if root_cause_result and root_cause_result.output:
            root_causes = root_cause_result.output.get("root_causes", [])

        primary_category = (
            root_causes[0]["category"] if root_causes else "unknown"
        )

        # Build order lookup for enrichment.
        order_lookup: dict[str, dict[str, Any]] = {
            o.get("order_id", ""): o for o in ctx.order_history
        }

        all_scenarios: list[dict[str, Any]] = []

        for incident in incidents:
            order_id = incident.get("order_id", "")
            order = order_lookup.get(order_id, {})
            incident_scenarios = self._evaluate_scenarios(
                incident, order, primary_category
            )
            all_scenarios.extend(incident_scenarios)

        return self._success(
            output={"scenarios": all_scenarios},
            message=f"Evaluated {len(all_scenarios)} counterfactual scenarios.",
            confidence=0.65,
        )

    # --- Scenario evaluation ---

    def _evaluate_scenarios(
        self,
        incident: dict[str, Any],
        order: dict[str, Any],
        primary_category: str,
    ) -> list[dict[str, Any]]:
        """Generate counterfactual scenarios for a single incident."""
        order_id = incident.get("order_id", "unknown")
        incident_type = incident.get("type", "")
        scenarios: list[dict[str, Any]] = []

        # Scenario 1: Half-size order
        scenarios.append(
            self._scenario_half_size(order_id, incident_type, order)
        )

        # Scenario 2: Delayed entry (1 min)
        scenarios.append(
            self._scenario_delayed_entry(order_id, incident_type, primary_category)
        )

        # Scenario 3: Limit order instead of market
        scenarios.append(
            self._scenario_limit_order(order_id, incident_type, order)
        )

        # Scenario 4: Skip trade entirely
        scenarios.append(
            self._scenario_skip_trade(order_id, incident_type, order)
        )

        return scenarios

    def _scenario_half_size(
        self,
        order_id: str,
        incident_type: str,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """What if order was 50% size?"""
        estimated_outcome = "Loss reduced proportionally by ~50%"
        likely_improvement = "moderate"

        # If the incident is sizing-related, improvement is higher.
        if incident_type in ("large_loss", "slippage_breach"):
            pnl = order.get("realized_pnl")
            if pnl is not None:
                try:
                    half_pnl = Decimal(str(pnl)) / Decimal("2")
                    estimated_outcome = (
                        f"Estimated PnL at half size: {half_pnl}"
                    )
                    likely_improvement = "high"
                except (ArithmeticError, ValueError):
                    pass

        return {
            "order_id": order_id,
            "name": "half_size",
            "description": "Order placed at 50% of original size",
            "estimated_outcome": estimated_outcome,
            "likely_improvement": likely_improvement,
        }

    def _scenario_delayed_entry(
        self,
        order_id: str,
        incident_type: str,
        primary_category: str,
    ) -> dict[str, Any]:
        """What if entry was delayed by 1 minute?"""
        if primary_category == "market":
            estimated_outcome = (
                "Delayed entry may have caught a better price after "
                "initial volatility spike subsided."
            )
            likely_improvement = "moderate"
        elif primary_category == "exchange":
            estimated_outcome = (
                "Delayed entry may have avoided exchange congestion "
                "or rate limits."
            )
            likely_improvement = "moderate"
        else:
            estimated_outcome = (
                "Delayed entry unlikely to materially change outcome "
                "for this incident type."
            )
            likely_improvement = "low"

        return {
            "order_id": order_id,
            "name": "delayed_entry_1min",
            "description": "Entry delayed by 1 minute",
            "estimated_outcome": estimated_outcome,
            "likely_improvement": likely_improvement,
        }

    def _scenario_limit_order(
        self,
        order_id: str,
        incident_type: str,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """What if limit order instead of market?"""
        order_type = str(order.get("order_type", "")).upper()

        if order_type == "MARKET" and incident_type == "slippage_breach":
            estimated_outcome = (
                "Limit order would have avoided slippage by setting a "
                "price ceiling; trade may not have filled."
            )
            likely_improvement = "high"
        elif order_type == "MARKET":
            estimated_outcome = (
                "Limit order would have provided price protection; "
                "fill is uncertain."
            )
            likely_improvement = "moderate"
        else:
            estimated_outcome = (
                "Order was already a limit order; no change expected."
            )
            likely_improvement = "none"

        return {
            "order_id": order_id,
            "name": "limit_instead_of_market",
            "description": "Limit order used instead of market order",
            "estimated_outcome": estimated_outcome,
            "likely_improvement": likely_improvement,
        }

    def _scenario_skip_trade(
        self,
        order_id: str,
        incident_type: str,
        order: dict[str, Any],
    ) -> dict[str, Any]:
        """What if the trade was skipped entirely?"""
        pnl = order.get("realized_pnl")
        if pnl is not None:
            try:
                pnl_dec = Decimal(str(pnl))
                if pnl_dec < 0:
                    estimated_outcome = (
                        f"Skipping would have avoided a loss of {pnl_dec}."
                    )
                    likely_improvement = "high"
                else:
                    estimated_outcome = (
                        f"Skipping would have missed a gain of {pnl_dec}."
                    )
                    likely_improvement = "negative"
            except (ArithmeticError, ValueError):
                estimated_outcome = "PnL data unparseable; outcome uncertain."
                likely_improvement = "unknown"
        else:
            estimated_outcome = (
                "No PnL data available; skipping would have avoided "
                "the incident but outcome is unclear."
            )
            likely_improvement = "unknown"

        return {
            "order_id": order_id,
            "name": "skip_trade",
            "description": "Trade skipped entirely",
            "estimated_outcome": estimated_outcome,
            "likely_improvement": likely_improvement,
        }

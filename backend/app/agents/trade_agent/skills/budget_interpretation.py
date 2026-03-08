"""
Budget Interpretation skill.

Reads the budget allocation dict and available capital to compute
deployment limits. This is the first skill in the pipeline and
gates how much capital the agent is allowed to deploy.

Deterministic, risk_level=HIGH because miscalculating the budget
could lead to over-deployment.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)


class BudgetInterpretationSkill(BaseSkill):
    """Interpret budget allocation dict into concrete capital limits."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "budget_interpretation"

    @property
    def name(self) -> str:
        return "Budget Interpretation"

    @property
    def description(self) -> str:
        return (
            "Reads the budget configuration and available capital to "
            "compute deployable capital, per-symbol limits, and reserves."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.HIGH

    @property
    def required_inputs(self) -> list[str]:
        return ["budget", "available_capital"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        budget = ctx.budget
        available_capital = ctx.available_capital

        # Extract budget parameters with safe defaults.
        max_deployment_pct = Decimal(
            str(budget.get("max_deployment_pct", "0.8"))
        )
        per_symbol_max_pct = Decimal(
            str(budget.get("per_symbol_max_pct", "0.2"))
        )

        # Clamp percentages to valid range [0, 1].
        max_deployment_pct = max(Decimal("0"), min(Decimal("1"), max_deployment_pct))
        per_symbol_max_pct = max(Decimal("0"), min(Decimal("1"), per_symbol_max_pct))

        deployable_capital = available_capital * max_deployment_pct
        per_symbol_limit = available_capital * per_symbol_max_pct
        reserved_capital = available_capital - deployable_capital

        return self._success(
            output={
                "available_capital": str(available_capital),
                "deployable_capital": str(deployable_capital),
                "per_symbol_limit": str(per_symbol_limit),
                "reserved_capital": str(reserved_capital),
                "max_deployment_pct": str(max_deployment_pct),
                "per_symbol_max_pct": str(per_symbol_max_pct),
            },
            message=(
                f"Deployable capital: {deployable_capital} "
                f"({max_deployment_pct * 100}% of {available_capital}). "
                f"Per-symbol limit: {per_symbol_limit}."
            ),
        )

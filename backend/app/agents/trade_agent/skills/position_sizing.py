"""
Position Sizing skill.

Allocates deployable capital across scored candidates, respecting
per-symbol limits. Uses volatility-aware sizing when volatility
data is available, otherwise falls back to equal-risk allocation.

Deterministic, risk_level=HIGH because sizing errors directly
affect capital at risk.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)


class PositionSizingSkill(BaseSkill):
    """Allocate capital across scored candidates proportional to scores."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "position_sizing"

    @property
    def name(self) -> str:
        return "Position Sizing"

    @property
    def description(self) -> str:
        return (
            "Allocates deployable capital proportionally to opportunity "
            "scores, capped by per-symbol limits. Supports volatility-"
            "aware and equal-risk sizing methods."
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
    def prerequisites(self) -> list[str]:
        return ["budget_interpretation", "opportunity_scoring"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        budget_output = ctx.upstream_results["budget_interpretation"].output
        scoring_output = ctx.upstream_results["opportunity_scoring"].output

        deployable = Decimal(budget_output["deployable_capital"])
        per_symbol_limit = Decimal(budget_output["per_symbol_limit"])

        ranked = scoring_output.get("ranked_candidates", [])
        no_trade = scoring_output.get("no_trade", False)

        # If opportunity scoring flagged no trade, propagate.
        if no_trade or not ranked:
            return self._success(
                output={
                    "allocations": {},
                    "sizing_method": "none",
                    "residual_cash": str(deployable),
                },
                message="No allocations - opportunity scoring flagged no trade.",
            )

        # Filter to tradeable candidates (score >= threshold).
        tradeable = [c for c in ranked if c["score"] >= 30]
        if not tradeable:
            return self._success(
                output={
                    "allocations": {},
                    "sizing_method": "none",
                    "residual_cash": str(deployable),
                },
                message="No candidates above score threshold.",
            )

        # Determine sizing method.
        has_volatility = self._has_volatility_data(tradeable, ctx)
        sizing_method = "volatility_aware" if has_volatility else "equal_risk"

        if has_volatility:
            allocations, residual = self._volatility_aware_sizing(
                tradeable, deployable, per_symbol_limit, ctx,
            )
        else:
            allocations, residual = self._score_proportional_sizing(
                tradeable, deployable, per_symbol_limit, ctx,
            )

        return self._success(
            output={
                "allocations": allocations,
                "sizing_method": sizing_method,
                "residual_cash": str(residual),
            },
            message=(
                f"Allocated capital to {len(allocations)} symbols "
                f"via {sizing_method}. Residual: {residual}."
            ),
        )

    # ------------------------------------------------------------------
    # Sizing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_volatility_data(candidates: list[dict], ctx: SkillContext) -> bool:
        """Check whether volatility data is available for all candidates."""
        for c in candidates:
            md = ctx.market_data.get(c["symbol"], {})
            if md.get("volatility") is None:
                return False
        return True

    @staticmethod
    def _score_proportional_sizing(
        candidates: list[dict],
        deployable: Decimal,
        per_symbol_limit: Decimal,
        ctx: SkillContext,
    ) -> tuple[dict, Decimal]:
        """Allocate proportional to scores, capped by per-symbol limit."""
        total_score = sum(c["score"] for c in candidates)
        if total_score <= 0:
            return {}, deployable

        allocations: dict[str, dict] = {}
        remaining = deployable

        for c in candidates:
            symbol = c["symbol"]
            weight = Decimal(str(c["score"])) / Decimal(str(total_score))
            raw_notional = deployable * weight

            # Cap at per-symbol limit.
            notional = min(raw_notional, per_symbol_limit, remaining)
            if notional <= 0:
                continue

            # Compute quantity from last price.
            md = ctx.market_data.get(symbol, {})
            last_price = Decimal(str(md.get("last_price", "0")))
            if last_price <= 0:
                continue

            quantity = (notional / last_price).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN,
            )
            actual_notional = quantity * last_price
            remaining -= actual_notional

            allocations[symbol] = {
                "quantity": str(quantity),
                "notional": str(actual_notional),
                "pct_of_budget": str(
                    (actual_notional / deployable * Decimal("100")).quantize(
                        Decimal("0.01"),
                    )
                )
                if deployable > 0
                else "0",
            }

        residual = max(remaining, Decimal("0"))
        return allocations, residual

    @staticmethod
    def _volatility_aware_sizing(
        candidates: list[dict],
        deployable: Decimal,
        per_symbol_limit: Decimal,
        ctx: SkillContext,
    ) -> tuple[dict, Decimal]:
        """
        Inverse-volatility sizing: lower volatility gets larger allocation.

        risk_budget_per_symbol = deployable / N
        position_size = risk_budget / volatility
        """
        inv_vols: list[tuple[str, Decimal, float]] = []
        for c in candidates:
            md = ctx.market_data.get(c["symbol"], {})
            vol = Decimal(str(md.get("volatility", "1")))
            if vol <= 0:
                vol = Decimal("1")
            inv_vol = Decimal("1") / vol
            inv_vols.append((c["symbol"], inv_vol, c["score"]))

        total_inv_vol = sum(iv for _, iv, _ in inv_vols)
        if total_inv_vol <= 0:
            return {}, deployable

        allocations: dict[str, dict] = {}
        remaining = deployable

        for symbol, inv_vol, score in inv_vols:
            weight = inv_vol / total_inv_vol
            raw_notional = deployable * weight

            notional = min(raw_notional, per_symbol_limit, remaining)
            if notional <= 0:
                continue

            md = ctx.market_data.get(symbol, {})
            last_price = Decimal(str(md.get("last_price", "0")))
            if last_price <= 0:
                continue

            quantity = (notional / last_price).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN,
            )
            actual_notional = quantity * last_price
            remaining -= actual_notional

            allocations[symbol] = {
                "quantity": str(quantity),
                "notional": str(actual_notional),
                "pct_of_budget": str(
                    (actual_notional / deployable * Decimal("100")).quantize(
                        Decimal("0.01"),
                    )
                )
                if deployable > 0
                else "0",
            }

        residual = max(remaining, Decimal("0"))
        return allocations, residual

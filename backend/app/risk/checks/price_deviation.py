"""
Price deviation risk check.

Validates that the limit price on an order is within
PRICE_DEVIATION_THRESHOLD of the current last/mid price.
Prevents fat-finger errors.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class PriceDeviationCheck(BaseRiskCheck):
    """Check that limit price does not deviate excessively from current market price."""

    @property
    def name(self) -> str:
        return "price_deviation"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        # Only relevant for orders with a price (limit-style)
        if ctx.price is None:
            return self._skip("No limit price on this order (market order).")

        threshold = ctx.settings.get(
            "PRICE_DEVIATION_THRESHOLD", Decimal("0.05")
        )

        # Use mid price if available, otherwise last price
        reference_price = ctx.mid_price or ctx.last_price
        if reference_price is None or reference_price <= Decimal("0"):
            return self._skip("No reference price available for deviation check.")

        deviation = abs(ctx.price - reference_price) / reference_price

        if deviation > threshold:
            return self._fail(
                f"Limit price {ctx.price} deviates {deviation:.4%} from "
                f"reference {reference_price} (threshold: {threshold:.2%}).",
                limit_price=str(ctx.price),
                reference_price=str(reference_price),
                deviation=str(deviation),
                threshold=str(threshold),
            )

        return self._pass(
            "Price within acceptable deviation.",
            limit_price=str(ctx.price),
            reference_price=str(reference_price),
            deviation=str(deviation),
            threshold=str(threshold),
        )

"""
Order size risk check.

Validates that order quantity does not exceed MAX_ORDER_QUANTITY
and that order notional value does not exceed MAX_ORDER_NOTIONAL.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class OrderSizeCheck(BaseRiskCheck):
    """Check that order quantity and notional are within configured limits."""

    @property
    def name(self) -> str:
        return "order_size"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_quantity = ctx.settings.get("MAX_ORDER_QUANTITY", Decimal("100"))
        max_notional = ctx.settings.get("MAX_ORDER_NOTIONAL", Decimal("10000"))

        # Check quantity limit
        if ctx.quantity > max_quantity:
            return self._fail(
                f"Order quantity {ctx.quantity} exceeds max {max_quantity}.",
                order_quantity=str(ctx.quantity),
                max_quantity=str(max_quantity),
            )

        # Calculate notional value
        price = ctx.price or ctx.last_price or Decimal("0")
        if price > Decimal("0"):
            notional = ctx.quantity * price
            if notional > max_notional:
                return self._fail(
                    f"Order notional {notional} exceeds max {max_notional}.",
                    notional=str(notional),
                    max_notional=str(max_notional),
                )

        return self._pass(
            "Order size within limits.",
            quantity=str(ctx.quantity),
            max_quantity=str(max_quantity),
        )

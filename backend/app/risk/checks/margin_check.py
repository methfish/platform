"""
Margin check for futures / margin trading.

Validates that there is sufficient available margin to support
the new order. This is a placeholder implementation that checks
the available_margin field in the context.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class MarginCheck(BaseRiskCheck):
    """Check that available margin is sufficient for the order."""

    @property
    def name(self) -> str:
        return "margin_check"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        available_margin = ctx.available_margin

        # Skip if margin data is not available (spot trading)
        if available_margin <= Decimal("0"):
            return self._skip(
                "Margin data not available; likely spot trading.",
                available_margin=str(available_margin),
            )

        price = ctx.price or ctx.last_price or Decimal("0")
        if price <= Decimal("0"):
            return self._skip("No price available for margin calculation.")

        order_notional = ctx.quantity * price

        # Estimate required margin using leverage from settings
        max_leverage = ctx.settings.get("MAX_LEVERAGE", Decimal("3.0"))
        if max_leverage <= Decimal("0"):
            max_leverage = Decimal("1.0")

        required_margin = order_notional / max_leverage

        # Add a safety buffer of 10%
        margin_buffer = ctx.settings.get(
            "MARGIN_SAFETY_BUFFER", Decimal("1.1")
        )
        required_with_buffer = required_margin * margin_buffer

        if required_with_buffer > available_margin:
            return self._fail(
                f"Insufficient margin: need {required_with_buffer} "
                f"but only {available_margin} available.",
                required_margin=str(required_margin),
                required_with_buffer=str(required_with_buffer),
                available_margin=str(available_margin),
                order_notional=str(order_notional),
            )

        return self._pass(
            "Sufficient margin available.",
            required_margin=str(required_margin),
            available_margin=str(available_margin),
        )

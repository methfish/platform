"""
Position limit risk check.

Validates that the resulting position after the order would not
exceed MAX_POSITION_NOTIONAL.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class PositionLimitCheck(BaseRiskCheck):
    """Check that position will not exceed maximum notional limit after order fills."""

    @property
    def name(self) -> str:
        return "position_limit"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_position_notional = ctx.settings.get(
            "MAX_POSITION_NOTIONAL", Decimal("50000")
        )

        price = ctx.price or ctx.last_price or Decimal("0")
        if price <= Decimal("0"):
            return self._skip("No price available to calculate position notional.")

        order_notional = ctx.quantity * price

        # Estimate resulting position notional
        current_notional = ctx.current_position_notional

        if ctx.side == "BUY":
            if ctx.current_position_side in ("LONG", "FLAT"):
                # Adding to long or opening long
                resulting_notional = current_notional + order_notional
            else:
                # Reducing short
                resulting_notional = abs(current_notional - order_notional)
        else:
            # SELL
            if ctx.current_position_side in ("SHORT", "FLAT"):
                # Adding to short or opening short
                resulting_notional = current_notional + order_notional
            else:
                # Reducing long
                resulting_notional = abs(current_notional - order_notional)

        if resulting_notional > max_position_notional:
            return self._fail(
                f"Resulting position notional {resulting_notional} "
                f"would exceed max {max_position_notional}.",
                resulting_notional=str(resulting_notional),
                max_position_notional=str(max_position_notional),
                current_notional=str(current_notional),
                order_notional=str(order_notional),
            )

        return self._pass(
            "Position within limits.",
            resulting_notional=str(resulting_notional),
            max_position_notional=str(max_position_notional),
        )

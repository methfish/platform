"""
Leverage risk check.

Validates that the effective leverage after the order does not
exceed the configured MAX_LEVERAGE. Primarily relevant for
futures/margin trading.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class LeverageCheck(BaseRiskCheck):
    """Check that leverage does not exceed the configured maximum."""

    @property
    def name(self) -> str:
        return "leverage"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_leverage = ctx.settings.get("MAX_LEVERAGE", Decimal("3.0"))

        current_leverage = ctx.total_leverage

        # Skip if leverage data is not available (spot-only accounts)
        if current_leverage <= Decimal("0"):
            return self._skip(
                "Leverage data not available (spot mode or not set).",
            )

        # Estimate additional leverage from this order
        price = ctx.price or ctx.last_price or Decimal("0")
        equity = ctx.current_equity

        if price <= Decimal("0") or equity <= Decimal("0"):
            return self._skip(
                "Insufficient data to calculate leverage impact.",
                price=str(price),
                equity=str(equity),
            )

        order_notional = ctx.quantity * price
        estimated_new_leverage = current_leverage + (order_notional / equity)

        if estimated_new_leverage > max_leverage:
            return self._fail(
                f"Estimated leverage {estimated_new_leverage:.2f}x would exceed "
                f"max {max_leverage:.2f}x.",
                current_leverage=str(current_leverage),
                estimated_leverage=str(estimated_new_leverage),
                max_leverage=str(max_leverage),
                order_notional=str(order_notional),
            )

        return self._pass(
            "Leverage within limits.",
            current_leverage=str(current_leverage),
            estimated_leverage=str(estimated_new_leverage),
            max_leverage=str(max_leverage),
        )

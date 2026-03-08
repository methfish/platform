"""
Order rate risk check.

Validates that the number of orders submitted per minute does not
exceed MAX_ORDERS_PER_MINUTE (sliding window).
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class OrderRateCheck(BaseRiskCheck):
    """Check that order submission rate is within the configured limit."""

    @property
    def name(self) -> str:
        return "order_rate"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_orders_per_minute = int(
            ctx.settings.get("MAX_ORDERS_PER_MINUTE", 30)
        )

        current_rate = ctx.orders_in_last_minute

        if current_rate >= max_orders_per_minute:
            return self._fail(
                f"Order rate {current_rate}/min exceeds max {max_orders_per_minute}/min.",
                orders_in_last_minute=current_rate,
                max_orders_per_minute=max_orders_per_minute,
            )

        # Warn at 80% of the limit
        warn_threshold = int(max_orders_per_minute * 0.8)
        if current_rate >= warn_threshold:
            return self._warn(
                f"Order rate {current_rate}/min approaching max "
                f"{max_orders_per_minute}/min.",
                orders_in_last_minute=current_rate,
                max_orders_per_minute=max_orders_per_minute,
            )

        return self._pass(
            "Order rate within limits.",
            orders_in_last_minute=current_rate,
            max_orders_per_minute=max_orders_per_minute,
        )

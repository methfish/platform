"""
Per-trade PnL threshold risk check.

Validates that the estimated potential loss from a single trade
does not exceed a configurable per-trade PnL threshold. This is
a placeholder implementation using configurable thresholds.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class PnlThresholdCheck(BaseRiskCheck):
    """Check that estimated per-trade risk is within threshold."""

    @property
    def name(self) -> str:
        return "pnl_threshold"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_per_trade_loss = ctx.settings.get(
            "MAX_PER_TRADE_LOSS", Decimal("1000")
        )

        price = ctx.price or ctx.last_price or Decimal("0")
        if price <= Decimal("0"):
            return self._skip("No price available for PnL threshold calculation.")

        # Estimate maximum loss as the full notional of the trade.
        # In practice, this would be refined with stop-loss levels,
        # volatility estimates, or VaR calculations.
        order_notional = ctx.quantity * price

        # Use a configurable percentage as worst-case scenario
        max_loss_pct = ctx.settings.get(
            "MAX_PER_TRADE_LOSS_PCT", Decimal("0.10")
        )
        estimated_max_loss = order_notional * max_loss_pct

        if estimated_max_loss > max_per_trade_loss:
            return self._fail(
                f"Estimated max loss {estimated_max_loss} exceeds "
                f"per-trade threshold {max_per_trade_loss}.",
                order_notional=str(order_notional),
                estimated_max_loss=str(estimated_max_loss),
                max_per_trade_loss=str(max_per_trade_loss),
                max_loss_pct=str(max_loss_pct),
            )

        return self._pass(
            "Per-trade PnL within threshold.",
            estimated_max_loss=str(estimated_max_loss),
            max_per_trade_loss=str(max_per_trade_loss),
        )

"""
Concentration risk check.

Validates that a single asset does not represent more than a
configurable percentage of the total portfolio notional.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class ConcentrationCheck(BaseRiskCheck):
    """Check that single-asset concentration does not exceed the limit."""

    @property
    def name(self) -> str:
        return "concentration"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_concentration_pct = ctx.settings.get(
            "MAX_CONCENTRATION_PCT", Decimal("0.40")
        )

        total_portfolio = ctx.total_portfolio_notional
        if total_portfolio <= Decimal("0"):
            return self._skip(
                "Total portfolio notional not available; concentration check skipped.",
            )

        # Calculate resulting position notional for this symbol
        price = ctx.price or ctx.last_price or Decimal("0")
        if price <= Decimal("0"):
            return self._skip("No price available for concentration calculation.")

        order_notional = ctx.quantity * price
        current_notional = ctx.current_position_notional

        if ctx.side == "BUY":
            resulting_notional = current_notional + order_notional
        else:
            resulting_notional = abs(current_notional - order_notional)

        concentration = resulting_notional / total_portfolio

        if concentration > max_concentration_pct:
            return self._fail(
                f"Concentration {concentration:.2%} for {ctx.symbol} would exceed "
                f"max {max_concentration_pct:.2%} of portfolio.",
                symbol=ctx.symbol,
                resulting_notional=str(resulting_notional),
                total_portfolio=str(total_portfolio),
                concentration_pct=str(concentration),
                max_concentration_pct=str(max_concentration_pct),
            )

        return self._pass(
            "Concentration within limits.",
            symbol=ctx.symbol,
            concentration_pct=str(concentration),
            max_concentration_pct=str(max_concentration_pct),
        )

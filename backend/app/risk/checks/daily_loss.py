"""
Daily loss risk check.

Validates that the aggregate daily realized loss has not exceeded
MAX_DAILY_LOSS. This is a critical circuit-breaker check.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class DailyLossCheck(BaseRiskCheck):
    """Check that daily realized losses have not exceeded the configured maximum."""

    @property
    def name(self) -> str:
        return "daily_loss"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_daily_loss = ctx.settings.get("MAX_DAILY_LOSS", Decimal("5000"))

        daily_pnl = ctx.daily_realized_pnl

        # Loss is represented as a negative PnL value.
        # MAX_DAILY_LOSS is a positive number representing the max tolerable loss.
        if daily_pnl < Decimal("0") and abs(daily_pnl) >= max_daily_loss:
            return self._fail(
                f"Daily loss {abs(daily_pnl)} has reached max {max_daily_loss}.",
                daily_pnl=str(daily_pnl),
                max_daily_loss=str(max_daily_loss),
            )

        # Warn if approaching the limit (80% threshold)
        warn_threshold = max_daily_loss * Decimal("0.8")
        if daily_pnl < Decimal("0") and abs(daily_pnl) >= warn_threshold:
            return self._warn(
                f"Daily loss {abs(daily_pnl)} approaching max {max_daily_loss} "
                f"(threshold: {warn_threshold}).",
                daily_pnl=str(daily_pnl),
                max_daily_loss=str(max_daily_loss),
                warn_threshold=str(warn_threshold),
            )

        return self._pass(
            "Daily loss within limits.",
            daily_pnl=str(daily_pnl),
            max_daily_loss=str(max_daily_loss),
        )

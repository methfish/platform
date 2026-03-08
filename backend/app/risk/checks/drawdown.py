"""
Drawdown risk check.

Validates that the current drawdown from peak equity does not
exceed a configurable threshold (MAX_DRAWDOWN_PCT).
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class DrawdownCheck(BaseRiskCheck):
    """Check that max drawdown from peak equity is within threshold."""

    @property
    def name(self) -> str:
        return "drawdown"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_drawdown_pct = ctx.settings.get(
            "MAX_DRAWDOWN_PCT", Decimal("0.05")
        )

        peak = ctx.peak_equity
        current = ctx.current_equity

        # Skip if equity data is not available
        if peak <= Decimal("0"):
            return self._skip(
                "Peak equity not set; drawdown check skipped.",
                peak_equity=str(peak),
            )

        drawdown = (peak - current) / peak

        if drawdown >= max_drawdown_pct:
            return self._fail(
                f"Drawdown {drawdown:.4%} from peak {peak} exceeds "
                f"max {max_drawdown_pct:.2%}.",
                drawdown_pct=str(drawdown),
                peak_equity=str(peak),
                current_equity=str(current),
                max_drawdown_pct=str(max_drawdown_pct),
            )

        # Warn at 80% of the threshold
        warn_threshold = max_drawdown_pct * Decimal("0.8")
        if drawdown >= warn_threshold:
            return self._warn(
                f"Drawdown {drawdown:.4%} approaching max {max_drawdown_pct:.2%}.",
                drawdown_pct=str(drawdown),
                peak_equity=str(peak),
                current_equity=str(current),
                max_drawdown_pct=str(max_drawdown_pct),
            )

        return self._pass(
            "Drawdown within limits.",
            drawdown_pct=str(drawdown),
            max_drawdown_pct=str(max_drawdown_pct),
        )

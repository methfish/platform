"""
Cancel rate risk check.

Validates that the cancel-to-fill ratio is not excessive.
High cancel-to-fill ratios may indicate problematic behavior
and can trigger exchange-level penalties.
"""

from __future__ import annotations

from decimal import Decimal

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class CancelRateCheck(BaseRiskCheck):
    """Check that the cancel-to-fill ratio is not excessive."""

    @property
    def name(self) -> str:
        return "cancel_rate"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        max_ratio = ctx.settings.get(
            "MAX_CANCEL_TO_FILL_RATIO", Decimal("10.0")
        )

        cancel_count = ctx.cancel_count
        fill_count = ctx.fill_count

        # Need a minimum number of events for this check to be meaningful
        minimum_events = 10
        total_events = cancel_count + fill_count
        if total_events < minimum_events:
            return self._skip(
                f"Insufficient data ({total_events} events) for cancel rate check.",
                cancel_count=cancel_count,
                fill_count=fill_count,
            )

        if fill_count == 0:
            if cancel_count > 0:
                return self._fail(
                    f"Cancel-to-fill ratio is infinite ({cancel_count} cancels, "
                    f"0 fills).",
                    cancel_count=cancel_count,
                    fill_count=fill_count,
                )
            return self._pass("No cancels or fills recorded.")

        ratio = Decimal(str(cancel_count)) / Decimal(str(fill_count))

        if ratio > max_ratio:
            return self._fail(
                f"Cancel-to-fill ratio {ratio:.2f} exceeds max {max_ratio}.",
                cancel_count=cancel_count,
                fill_count=fill_count,
                ratio=str(ratio),
                max_ratio=str(max_ratio),
            )

        # Warn at 80% of the limit
        warn_threshold = max_ratio * Decimal("0.8")
        if ratio >= warn_threshold:
            return self._warn(
                f"Cancel-to-fill ratio {ratio:.2f} approaching max {max_ratio}.",
                cancel_count=cancel_count,
                fill_count=fill_count,
                ratio=str(ratio),
                max_ratio=str(max_ratio),
            )

        return self._pass(
            "Cancel-to-fill ratio within limits.",
            ratio=str(ratio),
            max_ratio=str(max_ratio),
        )

"""
Duplicate order risk check.

Detects identical orders (same symbol, side, quantity, price)
submitted within a short time window (default 5 seconds).
Prevents accidental double-submissions.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


# Default dedup window in seconds
DEFAULT_DEDUP_WINDOW_SECONDS = 5


class DuplicateOrderCheck(BaseRiskCheck):
    """Check that no identical order was submitted in the last N seconds."""

    @property
    def name(self) -> str:
        return "duplicate_order"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        dedup_window = ctx.settings.get(
            "DUPLICATE_ORDER_WINDOW_SECONDS", DEFAULT_DEDUP_WINDOW_SECONDS
        )
        now = time.time()

        for recent in ctx.recent_orders:
            # Check if within time window
            order_time = recent.get("timestamp", 0)
            if isinstance(order_time, (int, float)):
                age = now - order_time
            else:
                # If timestamp is not numeric, skip this entry
                continue

            if age > dedup_window:
                continue

            # Check for matching fields
            matches = (
                recent.get("symbol", "").upper() == ctx.symbol.upper()
                and recent.get("side", "").upper() == ctx.side.upper()
                and Decimal(str(recent.get("quantity", "0"))) == ctx.quantity
                and self._prices_match(recent.get("price"), ctx.price)
            )

            if matches:
                return self._fail(
                    f"Duplicate order detected: {ctx.symbol} {ctx.side} "
                    f"{ctx.quantity}@{ctx.price} submitted {age:.1f}s ago.",
                    symbol=ctx.symbol,
                    side=ctx.side,
                    quantity=str(ctx.quantity),
                    price=str(ctx.price),
                    age_seconds=round(age, 1),
                )

        return self._pass("No duplicate order detected.")

    @staticmethod
    def _prices_match(
        recent_price: Any,
        order_price: Decimal | None,
    ) -> bool:
        """Compare prices, treating None/None as a match (market orders)."""
        if recent_price is None and order_price is None:
            return True
        if recent_price is None or order_price is None:
            return False
        return Decimal(str(recent_price)) == order_price

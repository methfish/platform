"""
PnL calculator - computes realized and unrealized profit/loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.enums import PositionSide
from app.models.position import Position


@dataclass
class PnLSummary:
    total_realized_pnl: Decimal = Decimal("0")
    total_unrealized_pnl: Decimal = Decimal("0")
    total_commission: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")
    position_count: int = 0

    @property
    def gross_pnl(self) -> Decimal:
        return self.total_realized_pnl + self.total_unrealized_pnl

    def to_dict(self) -> dict:
        return {
            "total_realized_pnl": str(self.total_realized_pnl),
            "total_unrealized_pnl": str(self.total_unrealized_pnl),
            "total_commission": str(self.total_commission),
            "net_pnl": str(self.net_pnl),
            "gross_pnl": str(self.gross_pnl),
            "position_count": self.position_count,
        }


def compute_pnl_summary(positions: list[Position]) -> PnLSummary:
    """Compute aggregate PnL from a list of positions."""
    summary = PnLSummary()
    for pos in positions:
        summary.total_realized_pnl += pos.realized_pnl
        summary.total_unrealized_pnl += pos.unrealized_pnl
        summary.total_commission += pos.total_commission
        if pos.side != PositionSide.FLAT.value and pos.quantity > 0:
            summary.position_count += 1

    summary.net_pnl = (
        summary.total_realized_pnl
        + summary.total_unrealized_pnl
        - summary.total_commission
    )
    return summary


def compute_unrealized_pnl(
    side: str,
    quantity: Decimal,
    avg_entry_price: Decimal,
    mark_price: Decimal,
) -> Decimal:
    """Compute unrealized PnL for a single position."""
    if quantity <= 0 or side == PositionSide.FLAT.value:
        return Decimal("0")

    if side == PositionSide.LONG.value:
        return quantity * (mark_price - avg_entry_price)
    elif side == PositionSide.SHORT.value:
        return quantity * (avg_entry_price - mark_price)
    return Decimal("0")

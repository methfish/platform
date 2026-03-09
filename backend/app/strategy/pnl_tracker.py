"""
Per-strategy real-time P&L tracking.

Uses FIFO matching for realized P&L calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


_ZERO = Decimal("0")


@dataclass
class StrategyPnL:
    """Real-time P&L tracking for a single strategy."""

    strategy_name: str = ""
    realized_pnl: Decimal = _ZERO
    unrealized_pnl: Decimal = _ZERO
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_volume: Decimal = _ZERO
    total_commission: Decimal = _ZERO
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # FIFO queue: list of (side, remaining_qty, price)
    _open_fills: list[dict[str, Decimal | str]] = field(default_factory=list)

    def record_fill(
        self,
        side: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = _ZERO,
    ) -> None:
        """Record a fill and compute realized P&L using FIFO."""
        self.total_trades += 1
        self.total_volume += quantity * price
        self.total_commission += commission

        # Try to match against opposite side fills (FIFO)
        remaining = quantity
        while remaining > _ZERO and self._open_fills:
            oldest = self._open_fills[0]
            if oldest["side"] == side:
                break  # Same side, can't match

            match_qty = min(remaining, oldest["remaining_qty"])
            if match_qty <= _ZERO:
                break

            # Calculate P&L for this match
            if side == "SELL":
                # We're selling, matched against a previous buy
                pnl = (price - oldest["price"]) * match_qty
            else:
                # We're buying, matched against a previous sell (short cover)
                pnl = (oldest["price"] - price) * match_qty

            self.realized_pnl += pnl
            if pnl > _ZERO:
                self.winning_trades += 1
            elif pnl < _ZERO:
                self.losing_trades += 1

            oldest["remaining_qty"] -= match_qty
            remaining -= match_qty

            if oldest["remaining_qty"] <= _ZERO:
                self._open_fills.pop(0)

        # Any remaining quantity becomes a new open fill
        if remaining > _ZERO:
            self._open_fills.append({
                "side": side,
                "remaining_qty": remaining,
                "price": price,
            })

    def update_unrealized(self, mark_price: Decimal) -> None:
        """Update unrealized P&L based on current market price."""
        self.unrealized_pnl = _ZERO
        for fill in self._open_fills:
            qty = fill["remaining_qty"]
            entry = fill["price"]
            if fill["side"] == "BUY":
                self.unrealized_pnl += (mark_price - entry) * qty
            else:
                self.unrealized_pnl += (entry - mark_price) * qty

    @property
    def net_pnl(self) -> Decimal:
        return self.realized_pnl + self.unrealized_pnl - self.total_commission

    @property
    def pnl_per_trade(self) -> Decimal:
        if self.total_trades == 0:
            return _ZERO
        return self.realized_pnl / self.total_trades

    @property
    def win_rate(self) -> float:
        matched = self.winning_trades + self.losing_trades
        if matched == 0:
            return 0.0
        return self.winning_trades / matched

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "net_pnl": str(self.net_pnl),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_volume": str(self.total_volume),
            "total_commission": str(self.total_commission),
            "pnl_per_trade": str(self.pnl_per_trade),
            "start_time": self.start_time.isoformat(),
        }

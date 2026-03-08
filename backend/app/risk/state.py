"""
Runtime risk state accumulators.

Tracks rolling counters and accumulators used by risk checks at runtime.
These values are NOT persisted across restarts; they represent
the current trading session state.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class RiskState:
    """
    Tracks runtime risk accumulators for the risk engine.

    Accumulators:
        - Daily realized PnL (aggregate and per-strategy).
        - Order rate (sliding window per minute).
        - Cancel and fill counts for cancel-to-fill ratio.
        - Peak equity for drawdown calculation.
    """

    # Daily PnL tracking
    _daily_pnl_aggregate: Decimal = field(default=Decimal("0"))
    _daily_pnl_by_strategy: dict[str, Decimal] = field(default_factory=dict)

    # Sliding window for order rate (timestamps of recent orders)
    _order_timestamps: deque[float] = field(default_factory=deque)
    _order_rate_window_seconds: int = 60

    # Cancel / fill counters
    _cancel_count: int = 0
    _fill_count: int = 0

    # Equity tracking for drawdown
    _peak_equity: Decimal = field(default=Decimal("0"))
    _current_equity: Decimal = field(default=Decimal("0"))

    # Session start timestamp
    _session_start: float = field(default_factory=time.time)

    # --- Daily PnL ---

    @property
    def daily_realized_pnl(self) -> Decimal:
        """Aggregate daily realized PnL across all strategies."""
        return self._daily_pnl_aggregate

    @property
    def daily_realized_pnl_by_strategy(self) -> dict[str, Decimal]:
        """Daily realized PnL keyed by strategy ID."""
        return dict(self._daily_pnl_by_strategy)

    def record_pnl(self, amount: Decimal, strategy_id: Optional[str] = None) -> None:
        """
        Record a realized PnL amount.

        Args:
            amount: The PnL amount (positive for profit, negative for loss).
            strategy_id: Optional strategy identifier.
        """
        self._daily_pnl_aggregate += amount
        if strategy_id is not None:
            current = self._daily_pnl_by_strategy.get(strategy_id, Decimal("0"))
            self._daily_pnl_by_strategy[strategy_id] = current + amount

    # --- Order Rate ---

    @property
    def orders_in_last_minute(self) -> int:
        """Number of orders submitted in the last 60 seconds."""
        self._prune_order_timestamps()
        return len(self._order_timestamps)

    def record_order(self) -> None:
        """Record that an order was submitted (for rate limiting)."""
        self._order_timestamps.append(time.time())

    def _prune_order_timestamps(self) -> None:
        """Remove timestamps older than the sliding window."""
        cutoff = time.time() - self._order_rate_window_seconds
        while self._order_timestamps and self._order_timestamps[0] < cutoff:
            self._order_timestamps.popleft()

    # --- Cancel / Fill Counts ---

    @property
    def cancel_count(self) -> int:
        """Total cancels in the current session."""
        return self._cancel_count

    @property
    def fill_count(self) -> int:
        """Total fills in the current session."""
        return self._fill_count

    @property
    def cancel_to_fill_ratio(self) -> Decimal:
        """
        Cancel-to-fill ratio.

        Returns Decimal("0") if no fills have occurred.
        """
        if self._fill_count == 0:
            return Decimal("0")
        return Decimal(str(self._cancel_count)) / Decimal(str(self._fill_count))

    def record_cancel(self) -> None:
        """Increment the cancel counter."""
        self._cancel_count += 1

    def record_fill(self) -> None:
        """Increment the fill counter."""
        self._fill_count += 1

    # --- Equity / Drawdown ---

    @property
    def peak_equity(self) -> Decimal:
        """Peak equity observed in the current session."""
        return self._peak_equity

    @property
    def current_equity(self) -> Decimal:
        """Current equity value."""
        return self._current_equity

    @property
    def drawdown_from_peak(self) -> Decimal:
        """
        Current drawdown as a decimal fraction of peak equity.

        Returns Decimal("0") if peak equity is zero.
        """
        if self._peak_equity == Decimal("0"):
            return Decimal("0")
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def update_equity(self, equity: Decimal) -> None:
        """
        Update current equity and peak equity tracking.

        Args:
            equity: The current total equity value.
        """
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity

    # --- Reset ---

    def reset_daily(self) -> None:
        """
        Reset daily accumulators.

        Called at the start of a new trading day to clear
        daily PnL and order rate counters.
        """
        self._daily_pnl_aggregate = Decimal("0")
        self._daily_pnl_by_strategy.clear()
        self._order_timestamps.clear()
        self._cancel_count = 0
        self._fill_count = 0

    def reset_all(self) -> None:
        """Reset all accumulators including equity tracking."""
        self.reset_daily()
        self._peak_equity = Decimal("0")
        self._current_equity = Decimal("0")
        self._session_start = time.time()

"""
Inventory tracker — position management with PnL attribution.

Tracks:
  - Net position (long or short quantity)
  - Average entry price (FIFO-simplified: running weighted average)
  - Realized PnL per trade
  - Unrealized PnL (mark-to-market)
  - PnL attribution: alpha vs spread vs slippage vs commission

Simplifying assumptions:
  A10. Single-symbol inventory (one symbol per engine instance).
  A11. No netting across multiple symbols.
  A12. Average-cost method for entry price (not strict FIFO).
       This is common in forex where positions are typically
       treated as a single net position.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.simulator.types import (
    InventorySnapshot,
    OrderSide,
    PnLAttribution,
    SimFill,
    SimulatorConfig,
)

logger = logging.getLogger("pensy.simulator.inventory")


@dataclass
class ClosedTrade:
    """Record of a realized round-trip trade."""

    entry_time: datetime
    exit_time: datetime
    side: str                       # Entry side: BUY or SELL
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    entry_commission: Decimal
    exit_commission: Decimal
    gross_pnl: Decimal              # Before costs
    net_pnl: Decimal                # After all costs
    attribution: PnLAttribution


class InventoryTracker:
    """
    Tracks position, equity, and PnL for a single symbol.

    All prices are mid-prices unless otherwise noted. The tracker
    distinguishes between execution price (which includes spread/slippage)
    and the theoretical mid-price for attribution purposes.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        self._config = config
        self._initial_capital = config.initial_capital

        # Position state
        self._net_qty: Decimal = Decimal("0")       # Positive = long, negative = short
        self._avg_entry_price: Decimal = Decimal("0")
        self._avg_entry_mid: Decimal = Decimal("0")  # Mid-price at entry (for attribution)

        # Cumulative PnL
        self._realized_pnl: Decimal = Decimal("0")
        self._total_commission: Decimal = Decimal("0")
        self._entry_commission: Decimal = Decimal("0")  # P2: track entry commissions separately
        self._attribution = PnLAttribution()

        # Equity tracking
        self._equity: Decimal = config.initial_capital
        self._peak_equity: Decimal = config.initial_capital

        # Trade log
        self._closed_trades: list[ClosedTrade] = []
        self._equity_curve: list[InventorySnapshot] = []

        # Fill tracking for entry attribution
        self._entry_fills: list[tuple[Decimal, Decimal, Decimal, datetime]] = []
        # Each entry: (qty, exec_price, mid_price, timestamp)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_fill(
        self,
        fill: SimFill,
        mid_price: Decimal,
    ) -> Optional[ClosedTrade]:
        """
        Apply a fill to the inventory.

        If the fill reduces the position (or flips it), realizes PnL.
        Returns a ClosedTrade if PnL was realized, None otherwise.

        The mid_price parameter is the theoretical mid at fill time,
        used for PnL attribution (alpha vs cost decomposition).
        """
        self._total_commission += fill.commission

        qty = fill.quantity
        if fill.side == OrderSide.SELL:
            qty = -qty  # Negative for sells

        old_net = self._net_qty
        new_net = old_net + qty

        closed_trade: Optional[ClosedTrade] = None

        # Case 1: Increasing position or opening from flat
        if self._same_direction(old_net, qty) or old_net == 0:
            self._add_to_position(qty, fill.price, mid_price, fill.timestamp)
            self._entry_commission += fill.commission  # P2: track entry commission

        # Case 2: Reducing position
        elif self._opposite_direction(old_net, qty):
            close_qty = min(abs(qty), abs(old_net))
            closed_trade = self._close_position(
                close_qty=close_qty,
                exit_price=fill.price,
                exit_mid=mid_price,
                exit_commission=fill.commission * (close_qty / abs(qty)),
                exit_time=fill.timestamp,
            )

            # If the fill is larger than the position, open the other side
            overshoot = abs(qty) - abs(old_net)
            if overshoot > 0:
                flip_side_qty = overshoot if qty > 0 else -overshoot
                self._net_qty = Decimal("0")
                self._avg_entry_price = Decimal("0")
                self._avg_entry_mid = Decimal("0")
                self._entry_fills.clear()
                self._entry_commission = Decimal("0")  # P2: reset on flip
                # Commission for the overshoot portion goes to entry
                overshoot_commission = fill.commission * (overshoot / abs(qty))
                self._entry_commission += overshoot_commission
                self._add_to_position(
                    flip_side_qty, fill.price, mid_price, fill.timestamp,
                )

        self._net_qty = new_net
        return closed_trade

    def mark_to_market(self, mid_price: Decimal, timestamp: datetime) -> InventorySnapshot:
        """
        Mark the position to market and return a snapshot.

        Updates equity and drawdown tracking.
        """
        unrealized = self._compute_unrealized(mid_price)
        self._equity = self._initial_capital + self._realized_pnl + unrealized
        self._peak_equity = max(self._peak_equity, self._equity)

        dd_pct = 0.0
        if self._peak_equity > 0:
            dd_pct = float(
                (self._peak_equity - self._equity) / self._peak_equity * 100
            )

        # L0: Compute position notional and available margin
        pos_notional = abs(self._net_qty) * mid_price
        buying_power = self._config.buying_power(self._equity)
        available_margin = buying_power - pos_notional

        snap = InventorySnapshot(
            timestamp=timestamp,
            net_qty=self._net_qty,
            avg_entry_price=self._avg_entry_price,
            realized_pnl=self._realized_pnl,
            unrealized_pnl=unrealized,
            equity=self._equity,
            peak_equity=self._peak_equity,
            drawdown_pct=dd_pct,
            attribution=PnLAttribution(
                alpha=self._attribution.alpha,
                spread_cost=self._attribution.spread_cost,
                slippage_cost=self._attribution.slippage_cost,
                commission_cost=self._total_commission,
                realized_pnl=self._realized_pnl,
            ),
            position_notional=pos_notional,
            available_margin=available_margin,
        )
        self._equity_curve.append(snap)
        return snap

    @property
    def net_qty(self) -> Decimal:
        return self._net_qty

    @property
    def equity(self) -> Decimal:
        return self._equity

    @property
    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    @property
    def peak_equity(self) -> Decimal:
        return self._peak_equity

    @property
    def closed_trades(self) -> list[ClosedTrade]:
        return self._closed_trades

    @property
    def equity_curve(self) -> list[InventorySnapshot]:
        return self._equity_curve

    @property
    def total_commission(self) -> Decimal:
        return self._total_commission

    @property
    def is_flat(self) -> bool:
        return self._net_qty == 0

    @property
    def position_notional(self) -> Decimal:
        """Absolute notional value of the position at average entry."""
        return abs(self._net_qty) * self._avg_entry_price

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_to_position(
        self,
        qty: Decimal,
        exec_price: Decimal,
        mid_price: Decimal,
        timestamp: Optional[datetime],
    ) -> None:
        """Add to (or open) a position using weighted-average entry."""
        abs_qty = abs(qty)
        old_abs = abs(self._net_qty)
        new_abs = old_abs + abs_qty

        if new_abs > 0:
            # Weighted average entry
            self._avg_entry_price = (
                self._avg_entry_price * old_abs + exec_price * abs_qty
            ) / new_abs
            self._avg_entry_mid = (
                self._avg_entry_mid * old_abs + mid_price * abs_qty
            ) / new_abs
        else:
            self._avg_entry_price = exec_price
            self._avg_entry_mid = mid_price

        self._entry_fills.append((abs_qty, exec_price, mid_price, timestamp))

    def _close_position(
        self,
        close_qty: Decimal,
        exit_price: Decimal,
        exit_mid: Decimal,
        exit_commission: Decimal,
        exit_time: Optional[datetime],
    ) -> ClosedTrade:
        """Close (or reduce) the position and realize PnL."""
        # Determine entry side
        if self._net_qty > 0:
            entry_side = "BUY"
            gross_pnl = (exit_price - self._avg_entry_price) * close_qty
            alpha = (exit_mid - self._avg_entry_mid) * close_qty
        else:
            entry_side = "SELL"
            gross_pnl = (self._avg_entry_price - exit_price) * close_qty
            alpha = (self._avg_entry_mid - exit_mid) * close_qty

        # P2: Entry commission prorated from entry-only commissions
        total_fills_qty = sum(f[0] for f in self._entry_fills)
        if total_fills_qty > 0:
            entry_commission = self._entry_commission * (close_qty / total_fills_qty)
        else:
            entry_commission = Decimal("0")

        # Cost attribution
        spread_cost = abs(self._avg_entry_price - self._avg_entry_mid) * close_qty
        spread_cost += abs(exit_price - exit_mid) * close_qty
        slippage_cost = max(Decimal("0"), abs(gross_pnl - alpha) - spread_cost)

        total_cost = entry_commission + exit_commission
        net_pnl = gross_pnl - total_cost

        self._realized_pnl += net_pnl
        self._attribution.alpha += alpha
        self._attribution.spread_cost += spread_cost
        self._attribution.slippage_cost += slippage_cost
        self._attribution.realized_pnl += net_pnl

        # Get earliest entry time
        entry_time = exit_time
        if self._entry_fills:
            entry_time = self._entry_fills[0][3] or exit_time

        trade = ClosedTrade(
            entry_time=entry_time,
            exit_time=exit_time,
            side=entry_side,
            entry_price=self._avg_entry_price,
            exit_price=exit_price,
            quantity=close_qty,
            entry_commission=entry_commission,
            exit_commission=exit_commission,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            attribution=PnLAttribution(
                alpha=alpha,
                spread_cost=spread_cost,
                slippage_cost=slippage_cost,
                commission_cost=entry_commission + exit_commission,
                realized_pnl=net_pnl,
            ),
        )
        self._closed_trades.append(trade)

        # P2: Reduce entry commission proportionally
        if total_fills_qty > 0:
            self._entry_commission -= entry_commission

        # Reduce entry fills proportionally
        remaining_close = close_qty
        new_fills = []
        for fqty, fprice, fmid, ftime in self._entry_fills:
            if remaining_close <= 0:
                new_fills.append((fqty, fprice, fmid, ftime))
                continue
            if fqty <= remaining_close:
                remaining_close -= fqty
            else:
                new_fills.append((fqty - remaining_close, fprice, fmid, ftime))
                remaining_close = Decimal("0")
        self._entry_fills = new_fills

        return trade

    def _compute_unrealized(self, mid_price: Decimal) -> Decimal:
        """Compute unrealized PnL at the given mid price."""
        if self._net_qty == 0:
            return Decimal("0")
        if self._net_qty > 0:
            return (mid_price - self._avg_entry_price) * self._net_qty
        else:
            return (self._avg_entry_price - mid_price) * abs(self._net_qty)

    @staticmethod
    def _same_direction(net: Decimal, qty: Decimal) -> bool:
        return (net > 0 and qty > 0) or (net < 0 and qty < 0)

    @staticmethod
    def _opposite_direction(net: Decimal, qty: Decimal) -> bool:
        return (net > 0 and qty < 0) or (net < 0 and qty > 0)

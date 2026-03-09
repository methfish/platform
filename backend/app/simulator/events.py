"""
Event system — typed events and a timestamp-ordered priority queue.

All simulator state changes are driven by events. The engine processes
events in strict timestamp order. When two events share the same
timestamp, they are ordered by priority (lower = earlier).

Event priorities:
  0  MarketDataEvent      — bar arrives, updates L1 quotes
  1  OrderAckEvent        — order accepted onto the book
  2  CancelAckEvent       — cancel confirmed
  3  FillEvent            — full or partial fill
  4  KillSwitchEvent      — risk limit breached
  5  OrderSubmitEvent     — strategy wants to place an order (pre-latency)
  6  CancelRequestEvent   — strategy wants to cancel (pre-latency)
  7  ReplaceRequestEvent  — cancel-replace (pre-latency)
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from app.simulator.types import (
    OrderSide,
    SimBar,
    SimFill,
    SimOrder,
    SimOrderType,
    KillSwitchTrigger,
)


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass(order=False)
class SimEvent:
    """Base class for all simulator events."""

    timestamp: datetime
    priority: int = 99  # Lower = processed first at same timestamp

    def __lt__(self, other: SimEvent) -> bool:
        if self.timestamp == other.timestamp:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

    def __le__(self, other: SimEvent) -> bool:
        return self == other or self < other


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------


@dataclass(order=False)
class MarketDataEvent(SimEvent):
    """A new OHLCV bar has arrived."""

    priority: int = field(default=0, init=False)
    bar: SimBar = field(default_factory=SimBar)


# ---------------------------------------------------------------------------
# Order lifecycle
# ---------------------------------------------------------------------------


@dataclass(order=False)
class OrderSubmitEvent(SimEvent):
    """Strategy requests to place an order. Subject to latency delay."""

    priority: int = field(default=5, init=False)
    order: SimOrder = field(default_factory=SimOrder)


@dataclass(order=False)
class OrderAckEvent(SimEvent):
    """Order has been acknowledged by the exchange (post-latency)."""

    priority: int = field(default=1, init=False)
    order_id: str = ""


@dataclass(order=False)
class FillEvent(SimEvent):
    """An order has been (partially or fully) filled."""

    priority: int = field(default=3, init=False)
    fill: SimFill = field(default_factory=SimFill)


# ---------------------------------------------------------------------------
# Cancel / Replace
# ---------------------------------------------------------------------------


@dataclass(order=False)
class CancelRequestEvent(SimEvent):
    """Strategy requests to cancel an order. Subject to latency delay."""

    priority: int = field(default=6, init=False)
    order_id: str = ""


@dataclass(order=False)
class CancelAckEvent(SimEvent):
    """Cancel has been confirmed (post-latency)."""

    priority: int = field(default=2, init=False)
    order_id: str = ""
    remaining_qty: Decimal = Decimal("0")


@dataclass(order=False)
class ReplaceRequestEvent(SimEvent):
    """
    Cancel-replace: cancel the original order and submit a new one.
    Subject to cancel latency; new order subject to order latency after cancel ack.
    """

    priority: int = field(default=7, init=False)
    original_order_id: str = ""
    new_price: Optional[Decimal] = None
    new_quantity: Optional[Decimal] = None


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


@dataclass(order=False)
class KillSwitchEvent(SimEvent):
    """Kill switch has been triggered — all orders will be cancelled."""

    priority: int = field(default=4, init=False)
    trigger: KillSwitchTrigger = field(default_factory=KillSwitchTrigger)


# ---------------------------------------------------------------------------
# Event queue
# ---------------------------------------------------------------------------


class EventQueue:
    """
    Timestamp-ordered event priority queue.

    Uses a min-heap. Events at the same timestamp are ordered by
    priority, then by insertion order (FIFO tiebreaker).
    """

    def __init__(self) -> None:
        self._heap: list[tuple[datetime, int, int, SimEvent]] = []
        self._counter: int = 0  # FIFO tiebreaker

    def push(self, event: SimEvent) -> None:
        heapq.heappush(
            self._heap,
            (event.timestamp, event.priority, self._counter, event),
        )
        self._counter += 1

    def pop(self) -> SimEvent:
        _, _, _, event = heapq.heappop(self._heap)
        return event

    def peek(self) -> SimEvent | None:
        if self._heap:
            return self._heap[0][3]
        return None

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)

    def clear(self) -> None:
        self._heap.clear()
        self._counter = 0

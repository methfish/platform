"""
In-process async event bus for the Pensy platform.

Events are typed Python dataclasses. The event bus is a simple pub/sub
mechanism using asyncio. Events are notifications, NOT the source of truth.
Critical state is always persisted to PostgreSQL before events are emitted.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Coroutine
from uuid import UUID

logger = logging.getLogger(__name__)


# --- Event Types ---


@dataclass(frozen=True)
class Event:
    """Base event class. All events carry a timestamp and optional correlation_id."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = ""


@dataclass(frozen=True)
class OrderCreated(Event):
    order_id: UUID = field(default_factory=UUID.__new__)
    client_order_id: str = ""
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    quantity: Decimal = Decimal("0")
    price: Decimal | None = None


@dataclass(frozen=True)
class OrderStatusChanged(Event):
    order_id: UUID = field(default_factory=UUID.__new__)
    old_status: str = ""
    new_status: str = ""
    reason: str = ""


@dataclass(frozen=True)
class OrderFilled(Event):
    order_id: UUID = field(default_factory=UUID.__new__)
    fill_id: UUID = field(default_factory=UUID.__new__)
    symbol: str = ""
    side: str = ""
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")


@dataclass(frozen=True)
class PositionUpdated(Event):
    symbol: str = ""
    exchange: str = ""
    side: str = ""
    quantity: Decimal = Decimal("0")
    avg_entry_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class RiskCheckCompleted(Event):
    order_id: UUID = field(default_factory=UUID.__new__)
    passed: bool = False
    failed_checks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KillSwitchToggled(Event):
    activated: bool = False
    actor: str = ""


@dataclass(frozen=True)
class MarketDataUpdate(Event):
    symbol: str = ""
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    last: Decimal = Decimal("0")
    volume_24h: Decimal = Decimal("0")


@dataclass(frozen=True)
class ExchangeStatusChanged(Event):
    exchange: str = ""
    status: str = ""
    detail: str = ""


@dataclass(frozen=True)
class ReconciliationCompleted(Event):
    exchange: str = ""
    breaks_found: int = 0
    run_id: UUID = field(default_factory=UUID.__new__)


@dataclass(frozen=True)
class AlertTriggered(Event):
    severity: str = ""
    source: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# --- Event Bus ---

EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Simple in-process async event bus.

    Usage:
        bus = EventBus()
        bus.subscribe(OrderFilled, handle_fill)
        await bus.publish(OrderFilled(...))

    Handlers run concurrently via asyncio.gather. A failing handler
    does NOT prevent other handlers from executing.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = {}

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    async def publish(self, event: Event) -> None:
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        results = await asyncio.gather(
            *[self._safe_call(handler, event) for handler in handlers],
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Event handler failed",
                    extra={
                        "event_type": event_type.__name__,
                        "handler": handlers[i].__name__,
                        "error": str(result),
                    },
                )

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception(f"Error in event handler {handler.__name__}")
            raise


@dataclass(frozen=True)
class StrategyStarted(Event):
    strategy_name: str = ""
    strategy_type: str = ""


@dataclass(frozen=True)
class StrategyStopped(Event):
    strategy_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class StrategyPnLUpdate(Event):
    strategy_name: str = ""
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class AgentRunCompleted(Event):
    agent_type: str = ""
    completed: bool = True
    skills_run: int = 0
    skills_failed: int = 0
    total_time_ms: float = 0.0


@dataclass(frozen=True)
class SkillExecuted(Event):
    skill_id: str = ""
    agent_type: str = ""
    status: str = ""
    execution_time_ms: float = 0.0


# Global event bus instance
event_bus = EventBus()

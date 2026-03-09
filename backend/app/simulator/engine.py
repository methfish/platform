"""
Event-driven simulator engine.

Replays OHLCV bars as MarketDataEvents, processes strategy order
submissions through a latency model, and matches fills using the
FillModel. All state changes flow through the event queue.

Usage:
    config = SimulatorConfig(...)
    engine = SimulatorEngine(config)
    result = engine.run(bars, strategy_callback)

The strategy_callback receives (engine, bar) and calls engine.submit_order(),
engine.cancel_order(), or engine.replace_order() to interact.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional
from uuid import uuid4

from app.simulator.events import (
    CancelAckEvent,
    CancelRequestEvent,
    EventQueue,
    FillEvent,
    KillSwitchEvent,
    MarketDataEvent,
    OrderAckEvent,
    OrderSubmitEvent,
    ReplaceRequestEvent,
    SimEvent,
)
from app.simulator.fill_model import FillModel
from app.simulator.inventory import ClosedTrade, InventoryTracker
from app.simulator.kill_switch import KillSwitch
from app.simulator.types import (
    FillType,
    InventorySnapshot,
    KillSwitchTrigger,
    OrderSide,
    SimBar,
    SimFill,
    SimOrder,
    SimOrderStatus,
    SimOrderType,
    SimulatorConfig,
)

logger = logging.getLogger("pensy.simulator.engine")

# Type alias for the strategy callback
StrategyCallback = Callable[["SimulatorEngine", SimBar], None]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class SimulatorResult:
    """Output of a simulation run."""

    config: SimulatorConfig
    trades: list[ClosedTrade] = field(default_factory=list)
    equity_curve: list[InventorySnapshot] = field(default_factory=list)
    total_bars: int = 0
    total_fills: int = 0
    total_orders: int = 0
    total_cancels: int = 0
    total_rejects: int = 0
    kill_switch_trigger: Optional[KillSwitchTrigger] = None
    final_equity: Decimal = Decimal("0")
    final_pnl: Decimal = Decimal("0")
    events_processed: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SimulatorEngine:
    """
    Event-driven replay simulator.

    The engine:
      1. Enqueues all bars as MarketDataEvents.
      2. Processes events in timestamp order.
      3. On each MarketDataEvent:
         - Updates L1 quotes (bid/ask/mid derived from bar)
         - Checks resting limit orders for fills
         - Calls the strategy callback
      4. Strategy callback may call submit_order / cancel_order / replace_order
         which enqueue events with appropriate latency.
      5. Fill events update the inventory tracker.
      6. Kill switch is checked after every fill.
    """

    def __init__(self, config: SimulatorConfig) -> None:
        self._config = config
        self._queue = EventQueue()
        self._fill_model = FillModel(config)
        self._inventory = InventoryTracker(config)
        self._kill_switch = KillSwitch(config)

        # Order book
        self._orders: dict[str, SimOrder] = {}        # All orders by ID
        self._open_orders: dict[str, SimOrder] = {}   # Non-terminal orders

        # Current market state
        self._current_bar: Optional[SimBar] = None
        self._current_bid: Decimal = Decimal("0")
        self._current_ask: Decimal = Decimal("0")
        self._current_mid: Decimal = Decimal("0")

        # Counters
        self._total_fills = 0
        self._total_orders = 0
        self._total_cancels = 0
        self._total_rejects = 0
        self._events_processed = 0
        self._total_bars = 0

        # L8: Order deduplication — track client_ids submitted per bar
        self._bar_client_ids: set[str] = set()

        # L6: Gap detection state
        self._is_gap_bar: bool = False
        self._bar_duration_seconds: float = 0.0  # Estimated from first two bars

        # Strategy state (opaque dict for strategy use)
        self.state: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public: run simulation
    # ------------------------------------------------------------------

    def run(
        self,
        bars: list[SimBar],
        strategy: StrategyCallback,
    ) -> SimulatorResult:
        """
        Run the full simulation over the provided bars.

        Args:
            bars: OHLCV bars in chronological order.
            strategy: Callback invoked on each bar: strategy(engine, bar).
                      The strategy calls engine.submit_order() etc.

        Returns:
            SimulatorResult with trades, equity curve, and statistics.
        """
        if not bars:
            return SimulatorResult(config=self._config)

        # L6: Estimate bar duration from first two bars
        if len(bars) >= 2:
            self._bar_duration_seconds = (
                bars[1].timestamp - bars[0].timestamp
            ).total_seconds()

        # Enqueue all bars
        for bar in bars:
            self._queue.push(MarketDataEvent(timestamp=bar.timestamp, bar=bar))

        # Process events
        while self._queue:
            if self._kill_switch.is_active:
                self._cancel_all_open_orders()
                # Drain remaining market data events for equity curve
                self._drain_market_data_only()
                break

            event = self._queue.pop()
            self._events_processed += 1
            self._dispatch(event, strategy)

        # Close any remaining position at last bar's mid
        if self._current_bar and not self._inventory.is_flat:
            self._force_close_position()

        # Final snapshot
        if self._current_bar:
            self._inventory.mark_to_market(
                self._current_mid, self._current_bar.timestamp,
            )

        return SimulatorResult(
            config=self._config,
            trades=self._inventory.closed_trades,
            equity_curve=self._inventory.equity_curve,
            total_bars=self._total_bars,
            total_fills=self._total_fills,
            total_orders=self._total_orders,
            total_cancels=self._total_cancels,
            total_rejects=self._total_rejects,
            kill_switch_trigger=self._kill_switch.trigger,
            final_equity=self._inventory.equity,
            final_pnl=self._inventory.realized_pnl,
            events_processed=self._events_processed,
        )

    # ------------------------------------------------------------------
    # Public: live bar-by-bar processing (L7)
    # ------------------------------------------------------------------

    def step(
        self,
        bar: SimBar,
        strategy: StrategyCallback,
    ) -> InventorySnapshot:
        """
        L7: Process a single bar — for live bar-by-bar execution.

        Unlike run() which takes all bars upfront, step() processes one
        bar at a time. Call this repeatedly as new bars arrive from a
        live data feed.

        Returns the latest InventorySnapshot after processing this bar.
        """
        # Estimate bar duration from first two bars
        if self._total_bars == 1 and self._current_bar is not None:
            self._bar_duration_seconds = (
                bar.timestamp - self._current_bar.timestamp
            ).total_seconds()

        # Push this bar as a market data event
        self._queue.push(MarketDataEvent(timestamp=bar.timestamp, bar=bar))

        # Process all events up to and including this bar
        while self._queue:
            if self._kill_switch.is_active:
                self._cancel_all_open_orders()
                # Still process this bar for m2m
                event = self._queue.pop()
                self._events_processed += 1
                if isinstance(event, MarketDataEvent):
                    b = event.bar
                    self._current_bar = b
                    self._total_bars += 1
                    mid = b.typical
                    self._current_mid = mid
                    return self._inventory.mark_to_market(mid, b.timestamp)
                continue

            event = self._queue.pop()
            self._events_processed += 1
            self._dispatch(event, strategy)

        # Return the latest snapshot
        if self._inventory.equity_curve:
            return self._inventory.equity_curve[-1]
        return self._inventory.mark_to_market(
            self._current_mid, bar.timestamp,
        )

    async def step_async(
        self,
        bar: SimBar,
        strategy: StrategyCallback,
    ) -> InventorySnapshot:
        """
        L7: Async wrapper around step() for live trading integration.

        Runs step() in a way that doesn't block the event loop.
        Strategy callbacks can be async-aware by using engine.state
        to communicate with external async systems.
        """
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(
            None, self.step, bar, strategy,
        )

    def finalize(self) -> SimulatorResult:
        """
        L7: Finalize a live session — close positions and return result.

        Call this after the last step() to get the final SimulatorResult.
        Same as the tail of run() but without the event loop.
        """
        # Close any remaining position at last bar's mid
        if self._current_bar and not self._inventory.is_flat:
            self._force_close_position()

        # Final snapshot
        if self._current_bar:
            self._inventory.mark_to_market(
                self._current_mid, self._current_bar.timestamp,
            )

        return SimulatorResult(
            config=self._config,
            trades=self._inventory.closed_trades,
            equity_curve=self._inventory.equity_curve,
            total_bars=self._total_bars,
            total_fills=self._total_fills,
            total_orders=self._total_orders,
            total_cancels=self._total_cancels,
            total_rejects=self._total_rejects,
            kill_switch_trigger=self._kill_switch.trigger,
            final_equity=self._inventory.equity,
            final_pnl=self._inventory.realized_pnl,
            events_processed=self._events_processed,
        )

    @property
    def is_killed(self) -> bool:
        """Check if the kill switch has been triggered."""
        return self._kill_switch.is_active

    @property
    def current_bar(self) -> Optional[SimBar]:
        """The most recent bar processed."""
        return self._current_bar

    # ------------------------------------------------------------------
    # Public: strategy API (called from strategy callback)
    # ------------------------------------------------------------------

    def submit_order(
        self,
        side: OrderSide,
        quantity: Decimal,
        order_type: SimOrderType = SimOrderType.MARKET,
        price: Optional[Decimal] = None,
        client_id: str = "",
    ) -> str:
        """
        Submit an order. Returns the order ID.

        The order is subject to latency before it reaches the book.
        Market orders fill on the next event processing after latency.
        Limit orders are queued with a queue position.
        """
        if self._kill_switch.is_active:
            logger.warning("Order rejected: kill switch is active")
            self._total_rejects += 1
            return ""

        # L8: Duplicate order check (same client_id in same bar)
        if client_id and client_id in self._bar_client_ids:
            logger.warning("Order rejected: duplicate client_id %s in same bar", client_id)
            self._total_rejects += 1
            return ""

        if self._current_bar is None:
            logger.warning("Order rejected: no market data yet")
            self._total_rejects += 1
            return ""

        # P1: Pre-trade position limit check
        current_pos = abs(self._inventory.net_qty)
        if side == OrderSide.BUY and self._inventory.net_qty >= 0:
            projected = current_pos + quantity
        elif side == OrderSide.SELL and self._inventory.net_qty <= 0:
            projected = current_pos + quantity
        else:
            # Reducing position — always allowed
            projected = Decimal("0")
        if projected > self._config.max_position_qty:
            logger.warning(
                "Order rejected: projected position %s exceeds limit %s",
                projected, self._config.max_position_qty,
            )
            self._total_rejects += 1
            return ""

        # L0: Margin / buying power check
        if self._config.use_margin_check and projected > 0:
            projected_notional = projected * self._current_mid
            buying_power = self._config.buying_power(self._inventory.equity)
            if projected_notional > buying_power:
                logger.warning(
                    "Order rejected: projected notional %s exceeds buying power %s "
                    "(equity=%s, leverage=%s)",
                    projected_notional, buying_power,
                    self._inventory.equity, self._config.leverage,
                )
                self._total_rejects += 1
                return ""

        order = SimOrder(
            client_id=client_id or f"C-{uuid4().hex[:8]}",
            symbol=self._config.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=SimOrderStatus.PENDING,
            submit_time=self._current_bar.timestamp,
        )

        self._orders[order.order_id] = order
        self._total_orders += 1
        if client_id:
            self._bar_client_ids.add(client_id)

        # Enqueue with latency (L3: stochastic jitter)
        ack_time = self._current_bar.timestamp + self._order_latency()

        self._queue.push(OrderSubmitEvent(
            timestamp=ack_time,
            order=order,
        ))

        logger.debug(
            "Order submitted: %s %s %s qty=%s price=%s (ack at %s)",
            order.order_id, side.value, order_type.value,
            quantity, price, ack_time,
        )
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        """
        Request cancellation of an open order.

        Subject to cancel latency. Returns False if order not found or
        already terminal.
        """
        order = self._open_orders.get(order_id)
        if order is None or order.is_terminal:
            return False

        if order.status == SimOrderStatus.CANCEL_PENDING:
            return False  # Already pending cancel

        order.status = SimOrderStatus.CANCEL_PENDING

        cancel_time = self._current_bar.timestamp + self._cancel_latency()
        self._queue.push(CancelRequestEvent(
            timestamp=cancel_time,
            order_id=order_id,
        ))
        return True

    def replace_order(
        self,
        order_id: str,
        new_price: Optional[Decimal] = None,
        new_quantity: Optional[Decimal] = None,
    ) -> str:
        """
        Cancel-replace an order. Returns the new order ID.

        The cancel is subject to cancel latency. Once cancelled, a new
        order is submitted with order latency.
        """
        order = self._open_orders.get(order_id)
        if order is None or order.is_terminal:
            return ""

        cancel_time = self._current_bar.timestamp + self._cancel_latency()
        self._queue.push(ReplaceRequestEvent(
            timestamp=cancel_time,
            original_order_id=order_id,
            new_price=new_price,
            new_quantity=new_quantity,
        ))
        order.status = SimOrderStatus.CANCEL_PENDING
        return order_id  # Caller tracks original; new ID assigned on ack

    def get_open_orders(self) -> list[SimOrder]:
        """Return all non-terminal orders."""
        return [o for o in self._open_orders.values() if not o.is_terminal]

    def get_position(self) -> Decimal:
        """Return current net position quantity."""
        return self._inventory.net_qty

    def get_equity(self) -> Decimal:
        """Return current equity."""
        return self._inventory.equity

    def get_mid_price(self) -> Decimal:
        """Return current mid price."""
        return self._current_mid

    # ------------------------------------------------------------------
    # Latency helpers
    # ------------------------------------------------------------------

    def _order_latency(self) -> timedelta:
        """L3: Order latency with optional stochastic jitter."""
        base = self._config.order_latency_ms
        jitter = random.randint(0, self._config.latency_jitter_ms) if self._config.latency_jitter_ms > 0 else 0
        return timedelta(milliseconds=base + jitter)

    def _cancel_latency(self) -> timedelta:
        """L3: Cancel latency with optional stochastic jitter."""
        base = self._config.cancel_latency_ms
        jitter = random.randint(0, self._config.latency_jitter_ms) if self._config.latency_jitter_ms > 0 else 0
        return timedelta(milliseconds=base + jitter)

    # ------------------------------------------------------------------
    # Event dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, event: SimEvent, strategy: StrategyCallback) -> None:
        if isinstance(event, MarketDataEvent):
            self._on_market_data(event, strategy)
        elif isinstance(event, OrderSubmitEvent):
            self._on_order_submit(event)
        elif isinstance(event, OrderAckEvent):
            pass  # Handled inline in _on_order_submit
        elif isinstance(event, CancelRequestEvent):
            self._on_cancel_request(event)
        elif isinstance(event, CancelAckEvent):
            pass  # Handled inline in _on_cancel_request
        elif isinstance(event, ReplaceRequestEvent):
            self._on_replace_request(event)
        elif isinstance(event, FillEvent):
            self._on_fill(event)
        elif isinstance(event, KillSwitchEvent):
            self._on_kill_switch(event)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_market_data(
        self, event: MarketDataEvent, strategy: StrategyCallback,
    ) -> None:
        """Process a new bar: update quotes, check fills, call strategy."""
        bar = event.bar
        prev_bar = self._current_bar
        self._current_bar = bar
        self._total_bars += 1
        self._bar_client_ids.clear()  # L8: reset dedup per bar
        self._is_gap_bar = False  # L6: reset gap flag

        # L6: Detect weekend/holiday gaps
        if self._config.use_gap_detection and prev_bar is not None:
            gap_seconds = (bar.timestamp - prev_bar.timestamp).total_seconds()
            normal_seconds = self._bar_duration_seconds
            if normal_seconds > 0 and gap_seconds > normal_seconds * self._config.gap_threshold_multiplier:
                self._is_gap_bar = True
                logger.info(
                    "Gap detected: %s → %s (%.0f hours)",
                    prev_bar.timestamp, bar.timestamp, gap_seconds / 3600,
                )

        # Derive L1 quotes from bar (L1: dynamic spread when configured)
        mid = bar.typical
        half_spread = self._config.half_spread(mid, bar=bar)

        # L5: Scale spread by session multiplier
        if self._config.use_session_scaling:
            _, spread_mult = self._config.session_multipliers(bar.timestamp.hour)
            half_spread = half_spread * Decimal(str(spread_mult))

        # L6: Widen spread on gap bars
        if self._is_gap_bar:
            half_spread = half_spread * self._config.gap_spread_multiplier

        self._current_mid = mid
        self._current_bid = mid - half_spread
        self._current_ask = mid + half_spread

        # L4: Check partially-filled market orders for continued fills
        self._check_market_partials(bar)

        # Check resting limit orders for fills
        self._check_limit_fills(bar)

        # Mark to market
        snap = self._inventory.mark_to_market(mid, bar.timestamp)

        # P4: Check kill switch on every mark-to-market
        trigger = self._kill_switch.check(
            snapshot=snap,
            open_order_count=len(self._open_orders),
        )
        if trigger:
            self._queue.push(KillSwitchEvent(
                timestamp=bar.timestamp,
                trigger=trigger,
            ))
            return  # Don't call strategy if kill switch fired

        # Call strategy
        strategy(self, bar)

    def _on_order_submit(self, event: OrderSubmitEvent) -> None:
        """Order has arrived at the exchange (post-latency)."""
        order = event.order

        if order.is_terminal:
            return  # Was cancelled before ack

        order.status = SimOrderStatus.OPEN
        order.ack_time = event.timestamp
        self._open_orders[order.order_id] = order

        # Market orders: fill immediately
        if order.order_type == SimOrderType.MARKET:
            if self._current_bar:
                fill = self._fill_model.try_fill_market(order, self._current_bar)
                if fill:
                    self._apply_fill(order, fill)
                else:
                    order.status = SimOrderStatus.REJECTED
                    self._total_rejects += 1
                    self._open_orders.pop(order.order_id, None)
                    logger.warning("Market order rejected: no fill available")
            else:
                order.status = SimOrderStatus.REJECTED
                self._total_rejects += 1
                self._open_orders.pop(order.order_id, None)
            return

        # Limit orders: assign queue position
        if self._current_bar:
            self._fill_model.assign_queue_position(order, self._current_bar)

            # Check if the limit is immediately marketable
            # (BUY limit >= ask or SELL limit <= bid)
            if self._is_marketable(order):
                fill = self._fill_model.try_fill_market(order, self._current_bar)
                if fill:
                    # Marketable limit → taker fill at limit price
                    fill.price = order.price  # Fill at limit, not worse
                    fill.is_maker = False
                    fill.commission = (
                        fill.quantity * fill.price * self._config.taker_fee_rate
                    )
                    self._apply_fill(order, fill)

    def _on_cancel_request(self, event: CancelRequestEvent) -> None:
        """Cancel request has arrived at the exchange."""
        order = self._open_orders.get(event.order_id)
        if order is None or order.is_terminal:
            return

        remaining = order.remaining_qty
        order.status = SimOrderStatus.CANCELLED
        self._open_orders.pop(order.order_id, None)
        self._total_cancels += 1

        logger.debug(
            "Order cancelled: %s (remaining_qty=%s)",
            order.order_id, remaining,
        )

    def _on_replace_request(self, event: ReplaceRequestEvent) -> None:
        """Cancel-replace: cancel original, submit new order."""
        original = self._open_orders.get(event.original_order_id)
        if original is None or original.is_terminal:
            return

        # Cancel the original
        original.status = SimOrderStatus.CANCELLED
        self._open_orders.pop(original.order_id, None)
        self._total_cancels += 1

        # Submit replacement with order latency
        new_price = event.new_price or original.price
        new_qty = event.new_quantity or original.remaining_qty

        new_order = SimOrder(
            client_id=original.client_id,
            symbol=original.symbol,
            side=original.side,
            order_type=original.order_type,
            quantity=new_qty,
            price=new_price,
            status=SimOrderStatus.PENDING,
            submit_time=event.timestamp,
            original_order_id=original.order_id,
        )
        self._orders[new_order.order_id] = new_order
        self._total_orders += 1

        ack_time = event.timestamp + self._order_latency()
        self._queue.push(OrderSubmitEvent(timestamp=ack_time, order=new_order))

    def _on_fill(self, event: FillEvent) -> None:
        """Process a fill event (dispatched from _apply_fill)."""
        # Already processed in _apply_fill; this is for external fills
        pass

    def _on_kill_switch(self, event: KillSwitchEvent) -> None:
        """Kill switch event — cancel everything."""
        self._cancel_all_open_orders()

    # ------------------------------------------------------------------
    # Fill processing
    # ------------------------------------------------------------------

    def _apply_fill(self, order: SimOrder, fill: SimFill) -> None:
        """Apply a fill to the order and inventory."""
        order.filled_qty += fill.quantity
        order.avg_fill_price = (
            (order.avg_fill_price * (order.filled_qty - fill.quantity)
             + fill.price * fill.quantity)
            / order.filled_qty
        ) if order.filled_qty > 0 else fill.price
        order.total_commission += fill.commission
        order.last_fill_time = fill.timestamp

        if order.filled_qty >= order.quantity:
            order.status = SimOrderStatus.FILLED
            self._open_orders.pop(order.order_id, None)
        else:
            order.status = SimOrderStatus.PARTIALLY_FILLED

        self._total_fills += 1

        # Update inventory
        closed_trade = self._inventory.apply_fill(fill, self._current_mid)

        # Mark to market
        snap = self._inventory.mark_to_market(
            self._current_mid,
            fill.timestamp or self._current_bar.timestamp,
        )

        # Check kill switch
        trigger = self._kill_switch.check(
            snapshot=snap,
            open_order_count=len(self._open_orders),
            last_trade=closed_trade,
        )
        if trigger:
            self._queue.push(KillSwitchEvent(
                timestamp=fill.timestamp or self._current_bar.timestamp,
                trigger=trigger,
            ))

        logger.debug(
            "Fill: %s %s %s qty=%s @ %s (commission=%s, maker=%s)",
            fill.fill_id, fill.side.value,
            "FULL" if fill.fill_type == FillType.FULL else "PARTIAL",
            fill.quantity, fill.price, fill.commission, fill.is_maker,
        )

    def _check_market_partials(self, bar: SimBar) -> None:
        """L4: Continue filling partially-filled market orders on new bars."""
        for order in list(self._open_orders.values()):
            if order.order_type != SimOrderType.MARKET:
                continue
            if order.status != SimOrderStatus.PARTIALLY_FILLED:
                continue
            fill = self._fill_model.try_fill_market(order, bar)
            if fill:
                self._apply_fill(order, fill)

    def _check_limit_fills(self, bar: SimBar) -> None:
        """Check all resting limit orders for fills against the new bar."""
        for order in list(self._open_orders.values()):
            if order.order_type != SimOrderType.LIMIT:
                continue
            if order.status not in (SimOrderStatus.OPEN, SimOrderStatus.PARTIALLY_FILLED):
                continue

            fill = self._fill_model.try_fill_limit(order, bar)
            if fill:
                self._apply_fill(order, fill)

    def _is_marketable(self, order: SimOrder) -> bool:
        """Check if a limit order is immediately marketable."""
        if order.price is None:
            return False
        if order.side == OrderSide.BUY:
            return order.price >= self._current_ask
        else:
            return order.price <= self._current_bid

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cancel_all_open_orders(self) -> None:
        """Cancel all open orders (used by kill switch)."""
        for order in list(self._open_orders.values()):
            order.status = SimOrderStatus.CANCELLED
            self._total_cancels += 1
        self._open_orders.clear()

    def _force_close_position(self) -> None:
        """Force-close remaining position at current mid (end of simulation)."""
        if self._inventory.is_flat or self._current_bar is None:
            return

        qty = abs(self._inventory.net_qty)
        side = OrderSide.SELL if self._inventory.net_qty > 0 else OrderSide.BUY

        # Close at mid with taker costs
        mid = self._current_mid
        half_spread = self._config.half_spread(mid)
        if side == OrderSide.SELL:
            close_price = mid - half_spread
        else:
            close_price = mid + half_spread

        commission = qty * close_price * self._config.taker_fee_rate

        fill = SimFill(
            order_id="FORCE_CLOSE",
            symbol=self._config.symbol,
            side=side,
            fill_type=FillType.FULL,
            quantity=qty,
            price=close_price,
            commission=commission,
            is_maker=False,
            timestamp=self._current_bar.timestamp,
        )
        self._inventory.apply_fill(fill, mid)
        self._total_fills += 1

    def _drain_market_data_only(self) -> None:
        """After kill switch, drain remaining bars for equity curve only."""
        while self._queue:
            event = self._queue.pop()
            self._events_processed += 1
            if isinstance(event, MarketDataEvent):
                bar = event.bar
                self._current_bar = bar
                self._total_bars += 1
                mid = bar.typical
                self._current_mid = mid
                self._inventory.mark_to_market(mid, bar.timestamp)

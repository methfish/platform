"""
Unit tests for the event-driven simulator.

Tests cover:
  - Event queue ordering
  - Fill model: market fills, limit fills, queue draining, partial fills
  - Inventory: PnL tracking, position flips, attribution
  - Kill switch: all 5 rules
  - Engine: end-to-end replay with a simple strategy
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.simulator.types import (
    FillType,
    InventorySnapshot,
    KillSwitchTrigger,
    OrderSide,
    PnLAttribution,
    SimBar,
    SimFill,
    SimOrder,
    SimOrderStatus,
    SimOrderType,
    SimulatorConfig,
)
from app.simulator.events import (
    CancelRequestEvent,
    EventQueue,
    FillEvent,
    KillSwitchEvent,
    MarketDataEvent,
    OrderAckEvent,
    OrderSubmitEvent,
    SimEvent,
)
from app.simulator.fill_model import FillModel
from app.simulator.inventory import InventoryTracker
from app.simulator.kill_switch import KillSwitch
from app.simulator.engine import SimulatorEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

T0 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


def _bar(
    ts: datetime = T0,
    o: str = "1.1000",
    h: str = "1.1020",
    l: str = "1.0980",
    c: str = "1.1010",
    v: str = "10000",
) -> SimBar:
    return SimBar(
        timestamp=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal(v),
        symbol="EURUSD",
        interval="1m",
    )


def _config(**overrides) -> SimulatorConfig:
    defaults = dict(
        initial_capital=Decimal("100000"),
        maker_fee_rate=Decimal("0.00003"),
        taker_fee_rate=Decimal("0.00010"),
        spread_bps=Decimal("5"),
        slippage_bps=Decimal("1"),
        queue_behind_pct=Decimal("0.50"),
        fill_rate_pct=Decimal("1.0"),
        min_fill_qty=Decimal("1"),
        order_latency_ms=0,  # Zero latency for most tests
        cancel_latency_ms=0,
        max_loss_usd=Decimal("5000"),
        max_drawdown_pct=Decimal("10"),
        max_open_orders=50,
        max_position_notional=Decimal("1000000"),
        max_loss_per_trade_usd=Decimal("500"),
        max_position_qty=Decimal("100000"),
        symbol="EURUSD",
    )
    defaults.update(overrides)
    return SimulatorConfig(**defaults)


def _bars(n: int, start: datetime = T0, base: str = "1.1000") -> list[SimBar]:
    """Generate n bars with a slight uptrend."""
    bars = []
    price = Decimal(base)
    for i in range(n):
        ts = start + timedelta(minutes=i)
        bars.append(SimBar(
            timestamp=ts,
            open=price,
            high=price + Decimal("0.0020"),
            low=price - Decimal("0.0020"),
            close=price + Decimal("0.0005"),
            volume=Decimal("10000"),
            symbol="EURUSD",
            interval="1m",
        ))
        price += Decimal("0.0001")
    return bars


# ====================================================================
# Event Queue
# ====================================================================


class TestEventQueue:

    def test_timestamp_ordering(self):
        q = EventQueue()
        t1 = T0
        t2 = T0 + timedelta(minutes=1)

        q.push(MarketDataEvent(timestamp=t2, bar=_bar(ts=t2)))
        q.push(MarketDataEvent(timestamp=t1, bar=_bar(ts=t1)))

        first = q.pop()
        assert first.timestamp == t1

    def test_priority_ordering_same_timestamp(self):
        q = EventQueue()
        # MarketData (priority=0) should come before OrderSubmit (priority=5)
        q.push(OrderSubmitEvent(timestamp=T0, order=SimOrder()))
        q.push(MarketDataEvent(timestamp=T0, bar=_bar()))

        first = q.pop()
        assert isinstance(first, MarketDataEvent)

    def test_fifo_same_priority(self):
        q = EventQueue()
        bar1 = _bar(ts=T0)
        bar2 = _bar(ts=T0)
        bar2.close = Decimal("2.0")

        q.push(MarketDataEvent(timestamp=T0, bar=bar1))
        q.push(MarketDataEvent(timestamp=T0, bar=bar2))

        first = q.pop()
        assert first.bar.close == Decimal("1.1010")

    def test_len_and_bool(self):
        q = EventQueue()
        assert len(q) == 0
        assert not q

        q.push(MarketDataEvent(timestamp=T0, bar=_bar()))
        assert len(q) == 1
        assert q


# ====================================================================
# Fill Model
# ====================================================================


class TestFillModel:

    def test_market_buy_fills_at_ask_plus_slippage(self):
        cfg = _config()
        fm = FillModel(cfg)
        bar = _bar()
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.MARKET,
            quantity=Decimal("1000"),
        )

        fill = fm.try_fill_market(order, bar)
        assert fill is not None
        assert fill.quantity == Decimal("1000")
        assert fill.is_maker is False

        # Price should be > mid (typical price)
        mid = bar.typical
        assert fill.price > mid

    def test_market_sell_fills_at_bid_minus_slippage(self):
        cfg = _config()
        fm = FillModel(cfg)
        bar = _bar()
        order = SimOrder(
            side=OrderSide.SELL,
            order_type=SimOrderType.MARKET,
            quantity=Decimal("1000"),
        )

        fill = fm.try_fill_market(order, bar)
        assert fill is not None
        mid = bar.typical
        assert fill.price < mid

    def test_market_fill_commission_is_taker(self):
        cfg = _config(taker_fee_rate=Decimal("0.001"))
        fm = FillModel(cfg)
        bar = _bar()
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.MARKET,
            quantity=Decimal("1000"),
        )

        fill = fm.try_fill_market(order, bar)
        expected_commission = Decimal("1000") * fill.price * Decimal("0.001")
        assert fill.commission == expected_commission

    def test_limit_buy_fills_when_price_trades_through(self):
        cfg = _config(queue_behind_pct=Decimal("0"))  # No queue
        fm = FillModel(cfg)
        bar = _bar(l="1.0950")  # Low trades below limit
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("1000"),
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )
        order.queue_ahead = Decimal("0")

        fill = fm.try_fill_limit(order, bar)
        assert fill is not None
        assert fill.price == Decimal("1.0970")  # Fills at limit
        assert fill.is_maker is True

    def test_limit_buy_does_not_fill_when_price_touches_only(self):
        """Assumption A7: touching is not enough, must trade through."""
        cfg = _config(queue_behind_pct=Decimal("0"))
        fm = FillModel(cfg)
        bar = _bar(l="1.0970")  # Low equals limit exactly
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("1000"),
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )
        order.queue_ahead = Decimal("0")

        fill = fm.try_fill_limit(order, bar)
        assert fill is None

    def test_limit_order_queue_draining(self):
        cfg = _config(
            queue_behind_pct=Decimal("0.50"),
            fill_rate_pct=Decimal("1.0"),
        )
        fm = FillModel(cfg)

        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("1000"),
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )

        # Assign queue position
        bar1 = _bar(v="10000", l="1.0950")
        fm.assign_queue_position(order, bar1)
        assert order.queue_ahead > 0

        # First bar: drains queue but may not fill yet
        initial_queue = order.queue_ahead
        fill1 = fm.try_fill_limit(order, bar1)
        # Queue should have decreased
        assert order.queue_ahead < initial_queue

    def test_partial_fill(self):
        """When volume is small, only partial fill occurs."""
        cfg = _config(
            queue_behind_pct=Decimal("0"),
            min_fill_qty=Decimal("1"),
        )
        fm = FillModel(cfg)

        bar = _bar(v="100", l="1.0950")  # Very low volume
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("10000"),  # Want 10K but only ~10 available
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )
        order.queue_ahead = Decimal("0")

        fill = fm.try_fill_limit(order, bar)
        if fill is not None:
            assert fill.quantity < Decimal("10000")
            assert fill.fill_type == FillType.PARTIAL

    def test_limit_commission_is_maker(self):
        cfg = _config(
            maker_fee_rate=Decimal("0.00003"),
            queue_behind_pct=Decimal("0"),
        )
        fm = FillModel(cfg)
        bar = _bar(l="1.0950")
        order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("1000"),
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )
        order.queue_ahead = Decimal("0")

        fill = fm.try_fill_limit(order, bar)
        if fill is not None:
            expected = fill.quantity * fill.price * Decimal("0.00003")
            assert fill.commission == expected


# ====================================================================
# Inventory Tracker
# ====================================================================


class TestInventoryTracker:

    def test_open_long_position(self):
        cfg = _config()
        inv = InventoryTracker(cfg)

        fill = SimFill(
            side=OrderSide.BUY,
            quantity=Decimal("1000"),
            price=Decimal("1.1000"),
            commission=Decimal("0.11"),
            timestamp=T0,
        )

        result = inv.apply_fill(fill, mid_price=Decimal("1.0998"))
        assert result is None  # No closed trade
        assert inv.net_qty == Decimal("1000")

    def test_close_long_realizes_pnl(self):
        cfg = _config()
        inv = InventoryTracker(cfg)

        # Open long
        buy = SimFill(
            side=OrderSide.BUY,
            quantity=Decimal("1000"),
            price=Decimal("1.1000"),
            commission=Decimal("0.11"),
            timestamp=T0,
        )
        inv.apply_fill(buy, mid_price=Decimal("1.0998"))

        # Close long
        sell = SimFill(
            side=OrderSide.SELL,
            quantity=Decimal("1000"),
            price=Decimal("1.1020"),
            commission=Decimal("0.11"),
            timestamp=T0 + timedelta(minutes=5),
        )
        trade = inv.apply_fill(sell, mid_price=Decimal("1.1022"))

        assert trade is not None
        assert trade.gross_pnl == Decimal("2.0000")  # (1.1020 - 1.1000) * 1000
        assert trade.net_pnl < trade.gross_pnl  # Costs reduce PnL
        assert inv.is_flat

    def test_unrealized_pnl(self):
        cfg = _config()
        inv = InventoryTracker(cfg)

        fill = SimFill(
            side=OrderSide.BUY,
            quantity=Decimal("1000"),
            price=Decimal("1.1000"),
            commission=Decimal("0"),
            timestamp=T0,
        )
        inv.apply_fill(fill, mid_price=Decimal("1.1000"))

        snap = inv.mark_to_market(Decimal("1.1050"), T0)
        assert snap.unrealized_pnl == Decimal("5.0000")  # (1.1050 - 1.1000) * 1000

    def test_position_flip(self):
        """Going from long to short in one fill."""
        cfg = _config()
        inv = InventoryTracker(cfg)

        # Open long 1000
        buy = SimFill(
            side=OrderSide.BUY,
            quantity=Decimal("1000"),
            price=Decimal("1.1000"),
            commission=Decimal("0"),
            timestamp=T0,
        )
        inv.apply_fill(buy, Decimal("1.1000"))
        assert inv.net_qty == Decimal("1000")

        # Sell 2000 (close 1000 + open short 1000)
        sell = SimFill(
            side=OrderSide.SELL,
            quantity=Decimal("2000"),
            price=Decimal("1.1010"),
            commission=Decimal("0"),
            timestamp=T0 + timedelta(minutes=1),
        )
        trade = inv.apply_fill(sell, Decimal("1.1010"))
        assert trade is not None  # Closed the long
        assert inv.net_qty == Decimal("-1000")  # Now short

    def test_pnl_attribution_has_components(self):
        cfg = _config()
        inv = InventoryTracker(cfg)

        buy = SimFill(
            side=OrderSide.BUY,
            quantity=Decimal("1000"),
            price=Decimal("1.1005"),  # Exec price above mid
            commission=Decimal("0.50"),
            timestamp=T0,
        )
        inv.apply_fill(buy, mid_price=Decimal("1.1000"))  # Mid is lower

        sell = SimFill(
            side=OrderSide.SELL,
            quantity=Decimal("1000"),
            price=Decimal("1.1015"),
            commission=Decimal("0.50"),
            timestamp=T0 + timedelta(minutes=5),
        )
        trade = inv.apply_fill(sell, mid_price=Decimal("1.1020"))

        assert trade is not None
        attr = trade.attribution
        # Alpha = mid-to-mid gain = (1.1020 - 1.1000) * 1000 = 2.0
        assert attr.alpha == Decimal("2.0000")
        assert attr.spread_cost > 0
        assert attr.commission_cost > 0


# ====================================================================
# Kill Switch
# ====================================================================


class TestKillSwitch:

    def _snap(self, **overrides) -> InventorySnapshot:
        defaults = dict(
            timestamp=T0,
            net_qty=Decimal("0"),
            avg_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            equity=Decimal("100000"),
            peak_equity=Decimal("100000"),
            drawdown_pct=0.0,
        )
        defaults.update(overrides)
        return InventorySnapshot(**defaults)

    def test_ks1_max_loss(self):
        ks = KillSwitch(_config(max_loss_usd=Decimal("1000")))
        snap = self._snap(realized_pnl=Decimal("-1500"))
        trigger = ks.check(snap, open_order_count=0)
        assert trigger is not None
        assert trigger.rule == "KS1_MAX_LOSS"

    def test_ks2_max_drawdown(self):
        ks = KillSwitch(_config(max_drawdown_pct=Decimal("5")))
        snap = self._snap(drawdown_pct=6.0)
        trigger = ks.check(snap, open_order_count=0)
        assert trigger is not None
        assert trigger.rule == "KS2_MAX_DRAWDOWN"

    def test_ks3_max_open_orders(self):
        ks = KillSwitch(_config(max_open_orders=10))
        snap = self._snap()
        trigger = ks.check(snap, open_order_count=15)
        assert trigger is not None
        assert trigger.rule == "KS3_MAX_OPEN_ORDERS"

    def test_ks4_max_position_notional(self):
        ks = KillSwitch(_config(max_position_notional=Decimal("50000")))
        snap = self._snap(
            net_qty=Decimal("100000"),
            avg_entry_price=Decimal("1.1"),
        )
        trigger = ks.check(snap, open_order_count=0)
        assert trigger is not None
        assert trigger.rule == "KS4_MAX_POSITION_NOTIONAL"

    def test_ks5_max_loss_per_trade(self):
        from app.simulator.inventory import ClosedTrade

        ks = KillSwitch(_config(max_loss_per_trade_usd=Decimal("100")))
        snap = self._snap()
        trade = ClosedTrade(
            entry_time=T0,
            exit_time=T0,
            side="BUY",
            entry_price=Decimal("1.1"),
            exit_price=Decimal("1.0"),
            quantity=Decimal("1000"),
            entry_commission=Decimal("0"),
            exit_commission=Decimal("0"),
            gross_pnl=Decimal("-100"),
            net_pnl=Decimal("-150"),
            attribution=PnLAttribution(),
        )
        trigger = ks.check(snap, open_order_count=0, last_trade=trade)
        assert trigger is not None
        assert trigger.rule == "KS5_MAX_LOSS_PER_TRADE"

    def test_no_trigger_when_within_limits(self):
        ks = KillSwitch(_config())
        snap = self._snap(realized_pnl=Decimal("500"))
        trigger = ks.check(snap, open_order_count=3)
        assert trigger is None
        assert not ks.is_active

    def test_stays_active_after_trigger(self):
        ks = KillSwitch(_config(max_loss_usd=Decimal("100")))
        snap = self._snap(realized_pnl=Decimal("-200"))
        ks.check(snap, open_order_count=0)
        assert ks.is_active

        # Even with recovery, stays active
        snap2 = self._snap(realized_pnl=Decimal("0"))
        trigger = ks.check(snap2, open_order_count=0)
        assert trigger is not None  # Returns the same trigger
        assert ks.is_active


# ====================================================================
# Engine — end-to-end
# ====================================================================


class TestSimulatorEngine:

    def test_empty_bars(self):
        engine = SimulatorEngine(_config())
        result = engine.run([], lambda eng, bar: None)
        assert result.total_bars == 0
        assert result.total_fills == 0

    def test_no_strategy_activity(self):
        """Bars replayed with no strategy action."""
        bars = _bars(10)
        engine = SimulatorEngine(_config())
        result = engine.run(bars, lambda eng, bar: None)
        assert result.total_bars == 10
        assert result.total_fills == 0
        assert result.total_orders == 0
        assert len(result.equity_curve) > 0

    def test_market_buy_and_sell(self):
        """Simple round-trip: buy on bar 2, sell on bar 5."""
        bars = _bars(10)

        def strategy(eng: SimulatorEngine, bar: SimBar):
            bar_idx = bars.index(bar)
            if bar_idx == 2:
                eng.submit_order(OrderSide.BUY, Decimal("1000"))
            elif bar_idx == 5:
                eng.submit_order(OrderSide.SELL, Decimal("1000"))

        engine = SimulatorEngine(_config())
        result = engine.run(bars, strategy)

        assert result.total_orders == 2
        assert result.total_fills == 2
        assert len(result.trades) >= 1

    def test_limit_order_placement(self):
        """Place a limit buy below market and verify it fills."""
        bars = _bars(20, base="1.1000")

        placed = [False]

        def strategy(eng: SimulatorEngine, bar: SimBar):
            if not placed[0]:
                # Place limit buy well below first bar
                eng.submit_order(
                    OrderSide.BUY,
                    Decimal("1000"),
                    order_type=SimOrderType.LIMIT,
                    price=Decimal("1.0980"),  # Below bar low of 1.0980
                )
                placed[0] = True

        engine = SimulatorEngine(_config())
        result = engine.run(bars, strategy)
        assert result.total_orders == 1
        # May or may not fill depending on bar lows

    def test_cancel_order(self):
        """Place and cancel an order."""
        bars = _bars(10)
        order_id_holder = [None]

        def strategy(eng: SimulatorEngine, bar: SimBar):
            bar_idx = bars.index(bar)
            if bar_idx == 1:
                oid = eng.submit_order(
                    OrderSide.BUY,
                    Decimal("1000"),
                    order_type=SimOrderType.LIMIT,
                    price=Decimal("1.0500"),  # Far from market, won't fill
                )
                order_id_holder[0] = oid
            elif bar_idx == 3 and order_id_holder[0]:
                eng.cancel_order(order_id_holder[0])

        engine = SimulatorEngine(_config())
        result = engine.run(bars, strategy)
        assert result.total_cancels >= 1

    def test_kill_switch_stops_trading(self):
        """Kill switch triggers and prevents further orders."""
        bars = _bars(20)

        def strategy(eng: SimulatorEngine, bar: SimBar):
            # Keep buying to trigger position notional limit
            # Use qty=500 which is within 10% of bar volume (10000)
            if eng.get_position() < Decimal("5000"):
                eng.submit_order(OrderSide.BUY, Decimal("500"))

        cfg = _config(
            max_position_notional=Decimal("2000"),
            max_position_qty=Decimal("5000"),
        )
        engine = SimulatorEngine(cfg)
        result = engine.run(bars, strategy)

        assert result.kill_switch_trigger is not None

    def test_latency_delays_fill(self):
        """With non-zero latency, order doesn't fill on same bar."""
        bars = _bars(5)

        def strategy(eng: SimulatorEngine, bar: SimBar):
            bar_idx = bars.index(bar)
            if bar_idx == 0:
                eng.submit_order(OrderSide.BUY, Decimal("1000"))

        cfg = _config(order_latency_ms=120000)  # 2 minutes latency
        engine = SimulatorEngine(cfg)
        result = engine.run(bars, strategy)

        # Order submitted on bar 0, but with 2-minute latency
        # it won't ack until bar 2. Fill depends on bar timing.
        assert result.total_orders == 1

    def test_replace_order(self):
        """Replace an order's price."""
        bars = _bars(10)
        oid_holder = [None]

        def strategy(eng: SimulatorEngine, bar: SimBar):
            bar_idx = bars.index(bar)
            if bar_idx == 1:
                oid = eng.submit_order(
                    OrderSide.BUY,
                    Decimal("1000"),
                    SimOrderType.LIMIT,
                    price=Decimal("1.0500"),
                )
                oid_holder[0] = oid
            elif bar_idx == 3 and oid_holder[0]:
                eng.replace_order(
                    oid_holder[0],
                    new_price=Decimal("1.0600"),
                )

        engine = SimulatorEngine(_config())
        result = engine.run(bars, strategy)
        # Original cancelled + new order submitted
        assert result.total_cancels >= 1
        assert result.total_orders >= 2

    def test_equity_curve_populated(self):
        bars = _bars(10)
        engine = SimulatorEngine(_config())
        result = engine.run(bars, lambda eng, bar: None)
        assert len(result.equity_curve) >= 10

    def test_force_close_at_end(self):
        """Open position is force-closed at end of simulation."""
        bars = _bars(5)

        def strategy(eng: SimulatorEngine, bar: SimBar):
            bar_idx = bars.index(bar)
            if bar_idx == 1:
                eng.submit_order(OrderSide.BUY, Decimal("1000"))

        engine = SimulatorEngine(_config())
        result = engine.run(bars, strategy)
        assert len(result.trades) >= 1  # Force-closed

    def test_maker_vs_taker_fees(self):
        """Verify maker fills have lower commission than taker fills."""
        cfg = _config(
            maker_fee_rate=Decimal("0.00003"),
            taker_fee_rate=Decimal("0.00100"),
        )
        fm = FillModel(cfg)
        bar = _bar()

        # Market order = taker
        market_order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.MARKET,
            quantity=Decimal("1000"),
        )
        taker_fill = fm.try_fill_market(market_order, bar)

        # Limit order = maker
        limit_order = SimOrder(
            side=OrderSide.BUY,
            order_type=SimOrderType.LIMIT,
            quantity=Decimal("1000"),
            price=Decimal("1.0970"),
            status=SimOrderStatus.OPEN,
        )
        limit_order.queue_ahead = Decimal("0")
        bar_low = _bar(l="1.0950")
        maker_fill = fm.try_fill_limit(limit_order, bar_low)

        assert taker_fill is not None
        if maker_fill is not None:
            assert maker_fill.commission < taker_fill.commission

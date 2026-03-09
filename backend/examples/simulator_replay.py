#!/usr/bin/env python3
"""
Example: SMA crossover strategy replayed through the event-driven simulator.

Demonstrates:
  - Building SimBars from synthetic OHLCV data
  - Submitting market and limit orders
  - Cancel-replace workflow
  - Inventory tracking with PnL attribution
  - Kill-switch behavior
  - Equity curve output

Run:
    cd backend && python -m examples.simulator_replay
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.simulator import (
    OrderSide,
    SimBar,
    SimOrderType,
    SimulatorConfig,
    SimulatorEngine,
)


# ---------------------------------------------------------------------------
# 1. Generate synthetic EURUSD bars (trending up then down)
# ---------------------------------------------------------------------------


def make_bars(n: int = 200) -> list[SimBar]:
    """Generate synthetic 1H bars with a trend reversal at the midpoint."""
    bars: list[SimBar] = []
    base = Decimal("1.08000")
    t0 = datetime(2025, 1, 2, 8, 0, 0, tzinfo=timezone.utc)

    for i in range(n):
        # Price walks up for the first half, then down
        if i < n // 2:
            drift = Decimal(str(i * 0.00015))
        else:
            drift = Decimal(str((n // 2) * 0.00015)) - Decimal(
                str((i - n // 2) * 0.00020)
            )

        mid = base + drift
        noise = Decimal("0.0003")
        bars.append(
            SimBar(
                timestamp=t0 + timedelta(hours=i),
                open=mid - noise,
                high=mid + noise * 2,
                low=mid - noise * 2,
                close=mid + noise,
                volume=Decimal("5000000"),  # 5M notional volume per bar
                symbol="EURUSD",
                interval="1h",
            )
        )
    return bars


# ---------------------------------------------------------------------------
# 2. Define a simple SMA crossover strategy
# ---------------------------------------------------------------------------


class SMAState:
    """Tracks SMA values across bars."""

    def __init__(self, fast: int = 10, slow: int = 30) -> None:
        self.fast_period = fast
        self.slow_period = slow
        self.closes: list[Decimal] = []

    def update(self, close: Decimal) -> tuple[Decimal | None, Decimal | None]:
        self.closes.append(close)
        fast_sma = None
        slow_sma = None
        if len(self.closes) >= self.fast_period:
            fast_sma = sum(self.closes[-self.fast_period :]) / self.fast_period
        if len(self.closes) >= self.slow_period:
            slow_sma = sum(self.closes[-self.slow_period :]) / self.slow_period
        return fast_sma, slow_sma


def sma_crossover_strategy(engine: SimulatorEngine, bar: SimBar) -> None:
    """
    SMA crossover strategy callback.

    - Buys 10,000 units when fast SMA crosses above slow SMA.
    - Sells 10,000 units when fast SMA crosses below slow SMA.
    - Uses limit orders 1 pip below/above mid for entries.
    - Demonstrates cancel-replace by adjusting unfilled limit orders.
    """
    # Initialize state on first call
    if "sma" not in engine.state:
        engine.state["sma"] = SMAState(fast=10, slow=30)
        engine.state["prev_signal"] = None
        engine.state["pending_entry_id"] = None

    sma: SMAState = engine.state["sma"]
    fast, slow = sma.update(bar.close)

    if fast is None or slow is None:
        return

    # Determine signal
    if fast > slow:
        signal = "BUY"
    elif fast < slow:
        signal = "SELL"
    else:
        signal = None

    prev = engine.state["prev_signal"]
    pos = engine.get_position()

    # On signal change: close existing position with market order, open new
    if signal != prev and signal is not None:
        # Cancel any pending limit entry
        pending_id = engine.state.get("pending_entry_id")
        if pending_id:
            engine.cancel_order(pending_id)
            engine.state["pending_entry_id"] = None

        # Close existing position
        if pos != 0:
            close_side = OrderSide.SELL if pos > 0 else OrderSide.BUY
            engine.submit_order(
                side=close_side,
                quantity=abs(pos),
                order_type=SimOrderType.MARKET,
            )

        # Open new position with a limit order 1 pip inside the market
        mid = engine.get_mid_price()
        if signal == "BUY":
            limit_px = mid - Decimal("0.0001")  # 1 pip below mid
            oid = engine.submit_order(
                side=OrderSide.BUY,
                quantity=Decimal("10000"),
                order_type=SimOrderType.LIMIT,
                price=limit_px,
                client_id="entry",
            )
        else:
            limit_px = mid + Decimal("0.0001")  # 1 pip above mid
            oid = engine.submit_order(
                side=OrderSide.SELL,
                quantity=Decimal("10000"),
                order_type=SimOrderType.LIMIT,
                price=limit_px,
                client_id="entry",
            )
        engine.state["pending_entry_id"] = oid

    # If we have a pending limit that hasn't filled after 5 bars, replace
    # with a more aggressive price (demonstrate cancel-replace)
    pending_id = engine.state.get("pending_entry_id")
    if pending_id:
        open_orders = engine.get_open_orders()
        for o in open_orders:
            if o.order_id == pending_id and o.filled_qty == 0:
                bars_waiting = engine.state.get("bars_since_entry", 0) + 1
                engine.state["bars_since_entry"] = bars_waiting
                if bars_waiting >= 5:
                    # Replace with market-crossing price to get filled
                    mid = engine.get_mid_price()
                    if o.side == OrderSide.BUY:
                        new_px = mid + Decimal("0.0001")
                    else:
                        new_px = mid - Decimal("0.0001")
                    engine.replace_order(pending_id, new_price=new_px)
                    engine.state["bars_since_entry"] = 0
                break
        else:
            # Order no longer open (filled or cancelled)
            engine.state["pending_entry_id"] = None
            engine.state["bars_since_entry"] = 0

    engine.state["prev_signal"] = signal


# ---------------------------------------------------------------------------
# 3. Run the simulation
# ---------------------------------------------------------------------------


def main() -> None:
    config = SimulatorConfig(
        initial_capital=Decimal("100000"),
        symbol="EURUSD",
        # Forex retail costs
        maker_fee_rate=Decimal("0"),
        taker_fee_rate=Decimal("0"),
        spread_bps=Decimal("15"),       # 1.5 pips
        slippage_bps=Decimal("1"),      # 0.1 pip
        # Latency
        order_latency_ms=50,
        cancel_latency_ms=50,
        # Kill switch
        max_loss_usd=Decimal("5000"),
        max_drawdown_pct=Decimal("5"),
        max_open_orders=20,
        max_position_notional=Decimal("500000"),
        max_loss_per_trade_usd=Decimal("500"),
        max_position_qty=Decimal("100000"),
    )

    bars = make_bars(200)
    engine = SimulatorEngine(config)
    result = engine.run(bars, sma_crossover_strategy)

    # -----------------------------------------------------------------------
    # 4. Print results
    # -----------------------------------------------------------------------

    print("=" * 70)
    print("SIMULATOR REPLAY RESULTS")
    print("=" * 70)
    print(f"Symbol:              {config.symbol}")
    print(f"Bars processed:      {result.total_bars}")
    print(f"Events processed:    {result.events_processed}")
    print(f"Total orders:        {result.total_orders}")
    print(f"Total fills:         {result.total_fills}")
    print(f"Total cancels:       {result.total_cancels}")
    print(f"Total rejects:       {result.total_rejects}")
    print(f"Final equity:        {result.final_equity:.2f}")
    print(f"Final PnL:           {result.final_pnl:.4f}")

    if result.kill_switch_trigger:
        t = result.kill_switch_trigger
        print(f"\nKILL SWITCH:         {t.rule} — {t.message}")

    # Trade log
    print(f"\n{'─' * 70}")
    print(f"CLOSED TRADES ({len(result.trades)})")
    print(f"{'─' * 70}")
    for i, trade in enumerate(result.trades, 1):
        attr = trade.attribution
        print(
            f"  #{i:>3}  {trade.side:4}  qty={trade.quantity:>10}  "
            f"entry={trade.entry_price:.5f}  exit={trade.exit_price:.5f}  "
            f"PnL={attr.realized_pnl:>+10.4f}  "
            f"(alpha={attr.alpha:>+.4f}  spread={attr.spread_cost:>+.4f}  "
            f"slip={attr.slippage_cost:>+.4f}  comm={attr.commission_cost:>+.4f})"
        )

    # Equity curve (sample every 10 bars)
    print(f"\n{'─' * 70}")
    print("EQUITY CURVE (sampled)")
    print(f"{'─' * 70}")
    print(f"  {'Timestamp':>22}  {'Equity':>12}  {'Pos':>8}  {'RealPnL':>10}  {'UnrealPnL':>10}  {'DD%':>6}")
    for snap in result.equity_curve[::10]:
        print(
            f"  {snap.timestamp.strftime('%Y-%m-%d %H:%M'):>22}  "
            f"{snap.equity:>12.2f}  {snap.net_qty:>8}  "
            f"{snap.realized_pnl:>10.4f}  {snap.unrealized_pnl:>10.4f}  "
            f"{snap.drawdown_pct:>6.2f}%"
        )

    print(f"\n{'=' * 70}")
    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Example: Full analytics report from a simulation run.

Generates synthetic bars, runs an SMA crossover strategy through
the simulator, then produces all 6 reports with both human-readable
and machine-readable (JSON) output.

Run:
    cd backend && python -m examples.analytics_report
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.simulator import (
    OrderSide,
    SimBar,
    SimOrderType,
    SimulatorConfig,
    SimulatorEngine,
)
from app.simulator.analytics import generate_full_report


# ---------------------------------------------------------------------------
# Bar generation (same as calibration_job but with more trades)
# ---------------------------------------------------------------------------


def make_bars(n: int = 500) -> list[SimBar]:
    random.seed(42)
    bars = []
    t0 = datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    price = 1.0800
    sigma_sq = 0.006 ** 2
    omega = sigma_sq * 0.05
    alpha = 0.10
    beta = 0.85
    epsilon = 0.0

    for i in range(n):
        sigma_sq = omega + alpha * epsilon ** 2 + beta * sigma_sq
        sigma = math.sqrt(sigma_sq)
        epsilon = random.gauss(0, sigma)
        new_price = price * math.exp(epsilon)
        move = abs(new_price - price)
        noise = max(move * 0.5, price * 0.00005)
        high = max(price, new_price) + abs(random.gauss(0, noise))
        low = min(price, new_price) - abs(random.gauss(0, noise))
        low = max(low, price * 0.95)
        volume = max(100000, 5_000_000 * random.uniform(0.5, 1.5))

        bars.append(SimBar(
            timestamp=t0 + timedelta(hours=i),
            open=Decimal(str(round(price, 5))),
            high=Decimal(str(round(high, 5))),
            low=Decimal(str(round(low, 5))),
            close=Decimal(str(round(new_price, 5))),
            volume=Decimal(str(round(volume, 0))),
            symbol="EURUSD",
            interval="1h",
        ))
        price = new_price
    return bars


# ---------------------------------------------------------------------------
# Strategy: SMA crossover with more aggressive trading
# ---------------------------------------------------------------------------


def sma_strategy(engine: SimulatorEngine, bar: SimBar) -> None:
    if "closes" not in engine.state:
        engine.state["closes"] = []
        engine.state["prev_signal"] = None

    engine.state["closes"].append(float(bar.close))
    closes = engine.state["closes"]

    fast_p, slow_p = 8, 20
    if len(closes) < slow_p:
        return

    fast_sma = sum(closes[-fast_p:]) / fast_p
    slow_sma = sum(closes[-slow_p:]) / slow_p

    signal = "BUY" if fast_sma > slow_sma else "SELL"
    prev = engine.state["prev_signal"]
    pos = engine.get_position()

    if signal != prev:
        # Close existing
        if pos != 0:
            side = OrderSide.SELL if pos > 0 else OrderSide.BUY
            engine.submit_order(side, abs(pos), SimOrderType.MARKET)

        # Open new
        qty = Decimal("10000")
        if signal == "BUY":
            engine.submit_order(OrderSide.BUY, qty, SimOrderType.MARKET)
        else:
            engine.submit_order(OrderSide.SELL, qty, SimOrderType.MARKET)

    engine.state["prev_signal"] = signal


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # 1. Generate bars and run simulation
    bars = make_bars(500)
    config = SimulatorConfig(
        initial_capital=Decimal("100000"),
        symbol="EURUSD",
        maker_fee_rate=Decimal("0.00003"),
        taker_fee_rate=Decimal("0.00010"),
        spread_bps=Decimal("10"),
        slippage_bps=Decimal("1"),
        order_latency_ms=0,
        cancel_latency_ms=0,
    )
    engine = SimulatorEngine(config)
    result = engine.run(bars, sma_strategy)

    # 2. Generate full report
    report = generate_full_report(result, bars)

    # 3. Print human-readable reports
    print(report.format())

    # 4. Print machine-readable JSON
    print("\n" + "=" * 70)
    print("MACHINE-READABLE OUTPUT (JSON)")
    print("=" * 70)
    d = report.to_dict()
    print(json.dumps(d, indent=2, default=str)[:3000])
    print(f"  ... ({len(json.dumps(d, default=str))} bytes total)")


if __name__ == "__main__":
    main()

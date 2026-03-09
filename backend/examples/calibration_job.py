#!/usr/bin/env python3
"""
Example: Walk-forward calibration job.

Generates synthetic EURUSD bars (with realistic volatility structure),
runs the full calibration pipeline, persists results, and prints a
calibration report showing the derived simulator parameters.

Run:
    cd backend && python -m examples.calibration_job

Output:
  1. Walk-forward calibration report with stability metrics
  2. Calibrated SimulatorConfig overrides ready to use
  3. Saved calibration snapshot to calibration_store/EURUSD/
"""

from __future__ import annotations

import math
import random
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.simulator.calibration import (
    ParameterStore,
    format_walk_forward_report,
    walk_forward_calibrate,
)
from app.simulator.types import SimBar, SimulatorConfig


# ---------------------------------------------------------------------------
# 1. Generate realistic synthetic bars
# ---------------------------------------------------------------------------


def make_realistic_bars(
    n: int = 1000,
    symbol: str = "EURUSD",
    base_price: float = 1.0800,
    daily_vol: float = 0.006,
    mean_volume: float = 5_000_000.0,
) -> list[SimBar]:
    """
    Generate synthetic 1H bars with realistic volatility clustering.

    Uses a simple GARCH(1,1)-like process for volatility:
      σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

    This produces realistic features:
      - Volatility clustering (high-vol periods followed by high-vol)
      - Fat tails in return distribution
      - Realistic high-low ranges relative to vol
    """
    random.seed(42)  # Reproducible

    bars: list[SimBar] = []
    t0 = datetime(2024, 1, 2, 8, 0, 0, tzinfo=timezone.utc)
    price = base_price

    # GARCH parameters
    omega = daily_vol ** 2 * 0.05
    alpha = 0.10
    beta = 0.85
    sigma_sq = daily_vol ** 2
    epsilon = 0.0

    for i in range(n):
        # Update GARCH volatility
        sigma_sq = omega + alpha * epsilon ** 2 + beta * sigma_sq
        sigma = math.sqrt(sigma_sq)

        # Generate return
        epsilon = random.gauss(0, sigma)
        new_price = price * math.exp(epsilon)

        # Generate OHLC from the return
        # High/Low extend beyond open/close by ~0.5-1.5× the move
        move = abs(new_price - price)
        noise = max(move * 0.5, price * 0.00005)
        high = max(price, new_price) + abs(random.gauss(0, noise))
        low = min(price, new_price) - abs(random.gauss(0, noise))
        low = max(low, price * 0.95)  # Safety floor

        # Volume with some clustering (correlated with volatility)
        vol_multiplier = 1.0 + 2.0 * (sigma / daily_vol - 1.0)
        volume = max(100_000, mean_volume * vol_multiplier * random.uniform(0.5, 1.5))

        bars.append(SimBar(
            timestamp=t0 + timedelta(hours=i),
            open=Decimal(str(round(price, 5))),
            high=Decimal(str(round(high, 5))),
            low=Decimal(str(round(low, 5))),
            close=Decimal(str(round(new_price, 5))),
            volume=Decimal(str(round(volume, 0))),
            symbol=symbol,
            interval="1h",
        ))

        price = new_price

    return bars


# ---------------------------------------------------------------------------
# 2. Run calibration
# ---------------------------------------------------------------------------


def main() -> None:
    print("Generating 1000 synthetic EURUSD 1H bars...")
    bars = make_realistic_bars(n=1000, symbol="EURUSD")
    print(f"  Price range: {min(float(b.low) for b in bars):.5f} – "
          f"{max(float(b.high) for b in bars):.5f}")
    print(f"  Date range:  {bars[0].timestamp.date()} – {bars[-1].timestamp.date()}")

    # Use a temp directory for the parameter store
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ParameterStore(base_dir=tmpdir)

        print("\nRunning walk-forward calibration...")
        result = walk_forward_calibrate(
            bars=bars,
            train_size=400,
            test_size=100,
            step_size=100,
            vol_window=20,
            fill_max_distance_bps=15.0,
            adverse_distance_bps=3.0,
            ofi_window=5,
            stability_cv_threshold=0.30,
            symbol="EURUSD",
            store=store,
        )

        # Print the full report
        report = format_walk_forward_report(result)
        print(report)

        # Show how to use the calibrated parameters
        if result.final_snapshot:
            overrides = result.final_snapshot.to_config_overrides()
            print("\n" + "=" * 70)
            print("USAGE: Apply calibrated parameters to SimulatorConfig")
            print("=" * 70)
            print()
            print("  from app.simulator import SimulatorConfig")
            print("  from app.simulator.calibration import ParameterStore")
            print()
            print("  store = ParameterStore('calibration_store')")
            print("  snapshot = store.load_latest('EURUSD')")
            print("  overrides = snapshot.to_config_overrides()")
            print("  config = SimulatorConfig(**overrides)")
            print()
            print("  # Or directly:")
            print("  config = SimulatorConfig(")
            for k, v in overrides.items():
                print(f'      {k}=Decimal("{v}"),')
            print("  )")

        # Verify the store persisted correctly
        loaded = store.load_latest("EURUSD")
        if loaded:
            print(f"\n  ✓ Calibration saved and reloaded successfully")
            print(f"    Parameters: {len(loaded.parameters)}")
            print(f"    Snapshots available: {store.list_snapshots('EURUSD')}")
        else:
            print("\n  ✗ Failed to reload calibration")


if __name__ == "__main__":
    main()

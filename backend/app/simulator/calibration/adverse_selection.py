"""
Adverse selection estimator.

Measures how much the mid-price moves against a hypothetical fill
at various horizons after the fill. This quantifies the "winner's
curse" — if your limit order fills, it's often because the market
moved through your price (adverse selection).

Method:
  For each bar where a hypothetical limit order would have filled:
    - Record the mid-price at fill time (bar's typical price)
    - Track the mid-price at horizons +1, +2, +5, +10 bars
    - Compute the signed move: positive = adverse (market moved
      against the filled side)

  adverse_selection(horizon) = E[signed_mid_move | filled]

Output:
  AdverseSelectionProfile with per-horizon adverse selection in bps.

This is critical for:
  1. Validating that slippage_bps in the simulator is realistic
  2. Understanding how much edge is consumed by adverse selection
  3. Deciding whether to use market or limit orders

Simplifying assumptions:
  C7. Hypothetical fills use the same "trades through" logic as A7.
  C8. Mid-price at fill = bar's typical price (same as simulator).
  C9. No position or inventory effect on adverse selection magnitude.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.simulator.types import SimBar


@dataclass
class HorizonResult:
    """Adverse selection at a single horizon."""

    horizon_bars: int
    buy_adverse_bps: float    # Mean adverse move for buy fills (positive = bad)
    sell_adverse_bps: float   # Mean adverse move for sell fills
    buy_n: int                # Number of buy fill observations
    sell_n: int
    buy_std_bps: float = 0.0  # Std dev of adverse moves
    sell_std_bps: float = 0.0


@dataclass
class AdverseSelectionProfile:
    """Adverse selection analysis across multiple horizons."""

    symbol: str
    n_bars: int
    limit_distance_bps: float
    horizons: list[HorizonResult] = field(default_factory=list)
    # Summary
    mean_buy_adverse_bps: float = 0.0   # Average across horizons
    mean_sell_adverse_bps: float = 0.0


def estimate_adverse_selection(
    bars: list[SimBar],
    limit_distance_bps: float = 3.0,
    horizons: Optional[list[int]] = None,
    symbol: str = "",
) -> AdverseSelectionProfile:
    """
    Estimate adverse selection after hypothetical limit order fills.

    For each bar, places hypothetical buy/sell limits at `limit_distance_bps`
    from mid. If the bar's range trades through the limit, records the
    subsequent mid-price movement at each horizon.

    Args:
        bars: Historical OHLCV bars.
        limit_distance_bps: Distance of hypothetical limit from mid (bps).
        horizons: List of forward horizons in bars. Default [1, 2, 5, 10, 20].
        symbol: Symbol name for labeling.
    """
    if horizons is None:
        horizons = [1, 2, 5, 10, 20]

    if len(bars) < max(horizons, default=0) + 1:
        return AdverseSelectionProfile(
            symbol=symbol,
            n_bars=len(bars),
            limit_distance_bps=limit_distance_bps,
        )

    # Precompute mid prices
    mids = [float((b.high + b.low + b.close)) / 3.0 for b in bars]

    horizon_results = []
    for h in horizons:
        buy_moves: list[float] = []
        sell_moves: list[float] = []

        for i in range(len(bars) - h):
            mid = mids[i]
            if mid <= 0:
                continue

            offset = mid * limit_distance_bps / 10000.0
            low = float(bars[i].low)
            high = float(bars[i].high)
            future_mid = mids[i + h]

            if future_mid <= 0:
                continue

            # Buy fill: low < mid − offset
            buy_limit = mid - offset
            if low < buy_limit:
                # Adverse for buy = mid dropped further (future_mid < fill_mid)
                # Convention: positive = adverse (market moved against you)
                move_bps = (mid - future_mid) / mid * 10000.0
                buy_moves.append(move_bps)

            # Sell fill: high > mid + offset
            sell_limit = mid + offset
            if high > sell_limit:
                # Adverse for sell = mid rose further
                move_bps = (future_mid - mid) / mid * 10000.0
                sell_moves.append(move_bps)

        buy_mean = sum(buy_moves) / len(buy_moves) if buy_moves else 0.0
        sell_mean = sum(sell_moves) / len(sell_moves) if sell_moves else 0.0
        buy_std = _std(buy_moves) if len(buy_moves) > 1 else 0.0
        sell_std = _std(sell_moves) if len(sell_moves) > 1 else 0.0

        horizon_results.append(HorizonResult(
            horizon_bars=h,
            buy_adverse_bps=buy_mean,
            sell_adverse_bps=sell_mean,
            buy_n=len(buy_moves),
            sell_n=len(sell_moves),
            buy_std_bps=buy_std,
            sell_std_bps=sell_std,
        ))

    # Summary: average across horizons
    mean_buy = (
        sum(r.buy_adverse_bps for r in horizon_results) / len(horizon_results)
        if horizon_results else 0.0
    )
    mean_sell = (
        sum(r.sell_adverse_bps for r in horizon_results) / len(horizon_results)
        if horizon_results else 0.0
    )

    return AdverseSelectionProfile(
        symbol=symbol,
        n_bars=len(bars),
        limit_distance_bps=limit_distance_bps,
        horizons=horizon_results,
        mean_buy_adverse_bps=mean_buy,
        mean_sell_adverse_bps=mean_sell,
    )


def recommended_slippage_bps(profile: AdverseSelectionProfile) -> float:
    """
    Derive a recommended slippage_bps for the simulator config.

    Uses the 1-bar horizon adverse selection as the baseline slippage,
    since that represents the immediate post-fill price impact.
    """
    for h in profile.horizons:
        if h.horizon_bars == 1:
            # Average of buy and sell adverse selection
            return (abs(h.buy_adverse_bps) + abs(h.sell_adverse_bps)) / 2.0
    return 1.0  # Default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _std(values: list[float]) -> float:
    """Sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)

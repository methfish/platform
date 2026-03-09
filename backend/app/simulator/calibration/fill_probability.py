"""
Fill probability estimator by quote distance.

Estimates the empirical probability that a limit order at distance `d`
from mid would have been filled, given historical bar data.

Method:
  For each bar, simulate hypothetical limit orders at distances
  [0.1, 0.2, ..., N] bps from the bar's mid price. A limit is considered
  "filled" if the bar's range traded through it (same logic as fill_model.py).

  fill_prob(d) = count(bars where low < mid − d) / total_bars   (for buys)
  fill_prob(d) = count(bars where high > mid + d) / total_bars  (for sells)

Output:
  A table of (distance_bps, fill_probability) pairs that can be used to:
    1. Calibrate the simulator's queue_behind_pct
    2. Inform limit order placement strategy
    3. Validate that the simulator's fill rates are realistic

Simplifying assumptions:
  C4. Fill means price traded through, not touched (matches simulator A7).
  C5. No time-of-day effect (fill probability is constant across hours).
  C6. Distance buckets are uniform in bps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.simulator.types import SimBar


@dataclass
class FillProbBucket:
    """Fill probability at a specific distance from mid."""

    distance_bps: float
    buy_fill_prob: float   # P(bar.low < mid − d)
    sell_fill_prob: float  # P(bar.high > mid + d)
    buy_fills: int
    sell_fills: int
    total_bars: int


@dataclass
class FillProbProfile:
    """Complete fill probability profile across distances."""

    symbol: str
    n_bars: int
    buckets: list[FillProbBucket] = field(default_factory=list)
    # Fitted parameters (optional, from logistic fit)
    buy_half_life_bps: Optional[float] = None   # Distance where P(fill) = 50%
    sell_half_life_bps: Optional[float] = None


def estimate_fill_probability(
    bars: list[SimBar],
    max_distance_bps: float = 20.0,
    step_bps: float = 0.5,
    symbol: str = "",
) -> FillProbProfile:
    """
    Estimate fill probability as a function of distance from mid.

    For each bar, checks whether a hypothetical limit order at each
    distance bucket would have been filled.

    Args:
        bars: Historical OHLCV bars.
        max_distance_bps: Maximum distance to check (in basis points).
        step_bps: Bucket width (in basis points).
        symbol: Symbol name for labeling.

    Returns:
        FillProbProfile with per-bucket fill probabilities.
    """
    if not bars:
        return FillProbProfile(symbol=symbol, n_bars=0)

    distances = _arange(step_bps, max_distance_bps + step_bps, step_bps)
    buy_counts = [0] * len(distances)
    sell_counts = [0] * len(distances)
    n = len(bars)

    for bar in bars:
        mid = float((bar.high + bar.low + bar.close)) / 3.0
        if mid <= 0:
            continue

        low = float(bar.low)
        high = float(bar.high)

        for i, d_bps in enumerate(distances):
            offset = mid * d_bps / 10000.0

            # Buy limit at mid − offset: fills if low < (mid − offset)
            buy_limit = mid - offset
            if low < buy_limit:
                buy_counts[i] += 1

            # Sell limit at mid + offset: fills if high > (mid + offset)
            sell_limit = mid + offset
            if high > sell_limit:
                sell_counts[i] += 1

    buckets = []
    for i, d_bps in enumerate(distances):
        buckets.append(FillProbBucket(
            distance_bps=d_bps,
            buy_fill_prob=buy_counts[i] / n if n > 0 else 0.0,
            sell_fill_prob=sell_counts[i] / n if n > 0 else 0.0,
            buy_fills=buy_counts[i],
            sell_fills=sell_counts[i],
            total_bars=n,
        ))

    profile = FillProbProfile(
        symbol=symbol,
        n_bars=n,
        buckets=buckets,
    )

    # Fit half-life (distance where fill prob drops to 50%)
    profile.buy_half_life_bps = _find_half_life(
        [(b.distance_bps, b.buy_fill_prob) for b in buckets]
    )
    profile.sell_half_life_bps = _find_half_life(
        [(b.distance_bps, b.sell_fill_prob) for b in buckets]
    )

    return profile


def recommended_spread_bps(profile: FillProbProfile, target_fill_pct: float = 0.50) -> Optional[float]:
    """
    Given a fill probability profile, find the distance where fill
    probability equals the target (default 50%).

    Useful for calibrating the simulator's spread_bps parameter.
    """
    for bucket in profile.buckets:
        # Use average of buy and sell
        avg_prob = (bucket.buy_fill_prob + bucket.sell_fill_prob) / 2.0
        if avg_prob <= target_fill_pct:
            return bucket.distance_bps
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _arange(start: float, stop: float, step: float) -> list[float]:
    """Simple float range (avoids numpy dependency)."""
    result = []
    val = start
    while val < stop + 1e-9:
        result.append(round(val, 4))
        val += step
    return result


def _find_half_life(
    pairs: list[tuple[float, float]],
    target: float = 0.50,
) -> Optional[float]:
    """
    Find the distance where probability crosses below target.

    Uses linear interpolation between the two bracketing points.
    """
    for i in range(1, len(pairs)):
        d_prev, p_prev = pairs[i - 1]
        d_curr, p_curr = pairs[i]
        if p_prev >= target >= p_curr and p_prev != p_curr:
            # Linear interpolation
            frac = (p_prev - target) / (p_prev - p_curr)
            return d_prev + frac * (d_curr - d_prev)
    return None

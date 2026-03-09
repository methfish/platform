"""
Queue depletion approximation.

Estimates how quickly the queue drains at various price levels from
historical OHLCV data. This calibrates two key simulator parameters:

  - queue_behind_pct: What fraction of bar volume is "ahead" of you
  - fill_rate_pct: How fast the queue drains per bar

Method:
  For a hypothetical limit order at distance D from mid:
    1. Count bars where the price eventually trades through D.
    2. Among those, count how many bars it takes from first touch
       to trade-through. This estimates the queue drain time.
    3. From drain time and bar volume, back out queue_behind_pct
       and fill_rate_pct.

The key insight: if a limit at distance D fills on bar N (trades
through), but first touched on bar M, then the queue took (N−M)
bars to drain. Combined with volume data, this gives us the drain
rate.

Simplifying assumptions:
  C14. Queue dynamics are approximated from bar-level data only.
  C15. "First touch" = first bar where bar.low ≤ limit (for buys).
  C16. "Trade through" = bar.low < limit (strict, matching A7).
  C17. Volume at the limit level follows the same uniform distribution
       as the simulator (A9).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.simulator.types import SimBar


@dataclass
class QueueEstimate:
    """Queue depletion estimate at a specific distance."""

    distance_bps: float
    # Mean bars from touch to trade-through
    mean_drain_bars: float
    median_drain_bars: float
    # Observations
    n_episodes: int          # Number of touch → trade-through episodes
    n_immediate: int         # Episodes that traded through on touch bar
    # Calibrated parameters
    implied_queue_behind_pct: float  # Fraction of volume ahead
    implied_fill_rate_pct: float     # Drain rate per bar


@dataclass
class QueueProfile:
    """Queue depletion analysis across multiple distances."""

    symbol: str
    n_bars: int
    estimates: list[QueueEstimate] = field(default_factory=list)
    # Recommended simulator parameters (averaged across distances)
    recommended_queue_behind_pct: float = 0.50
    recommended_fill_rate_pct: float = 1.0


def estimate_queue_depletion(
    bars: list[SimBar],
    distances_bps: Optional[list[float]] = None,
    symbol: str = "",
) -> QueueProfile:
    """
    Estimate queue depletion characteristics from bar data.

    For each distance, finds episodes where price first touches then
    later trades through the limit level. The number of bars between
    touch and trade-through estimates the queue drain time.

    Args:
        bars: Historical OHLCV bars.
        distances_bps: Distances from mid to analyze.
            Default [1, 2, 3, 5, 8, 10].
        symbol: Symbol name for labeling.
    """
    if distances_bps is None:
        distances_bps = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0]

    if len(bars) < 5:
        return QueueProfile(symbol=symbol, n_bars=len(bars))

    mids = [float((b.high + b.low + b.close)) / 3.0 for b in bars]
    estimates = []

    for d_bps in distances_bps:
        buy_drain_bars = _measure_drain_bars(bars, mids, d_bps, side="buy")
        sell_drain_bars = _measure_drain_bars(bars, mids, d_bps, side="sell")

        # Combine buy and sell
        all_drains = buy_drain_bars + sell_drain_bars
        n_immediate = sum(1 for d in all_drains if d == 0)

        if not all_drains:
            estimates.append(QueueEstimate(
                distance_bps=d_bps,
                mean_drain_bars=0.0,
                median_drain_bars=0.0,
                n_episodes=0,
                n_immediate=0,
                implied_queue_behind_pct=0.5,
                implied_fill_rate_pct=1.0,
            ))
            continue

        mean_drain = sum(all_drains) / len(all_drains)
        sorted_drains = sorted(all_drains)
        median_drain = float(sorted_drains[len(sorted_drains) // 2])

        # Back out simulator parameters from observed drain time.
        # Model: drain_bars = queue_behind_pct / fill_rate_pct
        # (since queue_ahead = queue_behind_pct × vol_at_level, and each bar
        #  drains fill_rate_pct × vol_at_level from queue_ahead)
        # With fill_rate_pct fixed at 1.0:
        #   queue_behind_pct ≈ mean_drain_bars × fill_rate_pct
        # Clamp to [0, 0.95] since >0.95 means nearly impossible fills.
        if mean_drain < 0.5:
            implied_queue = 0.0
            implied_rate = 1.0
        else:
            implied_rate = 1.0 / max(1.0, mean_drain)
            # queue_behind_pct = mean_drain × fill_rate (dimensional consistency)
            implied_queue = min(0.95, mean_drain * implied_rate)

        estimates.append(QueueEstimate(
            distance_bps=d_bps,
            mean_drain_bars=mean_drain,
            median_drain_bars=median_drain,
            n_episodes=len(all_drains),
            n_immediate=n_immediate,
            implied_queue_behind_pct=implied_queue,
            implied_fill_rate_pct=implied_rate,
        ))

    # Recommended parameters: weighted average across distances
    if estimates:
        total_episodes = sum(e.n_episodes for e in estimates)
        if total_episodes > 0:
            rec_queue = sum(
                e.implied_queue_behind_pct * e.n_episodes for e in estimates
            ) / total_episodes
            rec_rate = sum(
                e.implied_fill_rate_pct * e.n_episodes for e in estimates
            ) / total_episodes
        else:
            rec_queue = 0.50
            rec_rate = 1.0
    else:
        rec_queue = 0.50
        rec_rate = 1.0

    return QueueProfile(
        symbol=symbol,
        n_bars=len(bars),
        estimates=estimates,
        recommended_queue_behind_pct=rec_queue,
        recommended_fill_rate_pct=rec_rate,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _measure_drain_bars(
    bars: list[SimBar],
    mids: list[float],
    d_bps: float,
    side: str,
) -> list[int]:
    """
    Find touch-to-trade-through episodes and return drain bars for each.

    For buy limits: touch = bar.low ≤ limit, through = bar.low < limit.
    For sell limits: touch = bar.high ≥ limit, through = bar.high > limit.
    """
    drain_bars: list[int] = []
    touch_bar: Optional[int] = None

    for i, bar in enumerate(bars):
        mid = mids[i]
        if mid <= 0:
            continue

        offset = mid * d_bps / 10000.0
        low = float(bar.low)
        high = float(bar.high)

        if side == "buy":
            limit = mid - offset
            touched = low <= limit
            traded_through = low < limit
        else:
            limit = mid + offset
            touched = high >= limit
            traded_through = high > limit

        if traded_through:
            if touch_bar is not None:
                drain_bars.append(i - touch_bar)
            else:
                drain_bars.append(0)  # Immediate trade-through
            touch_bar = None
        elif touched and touch_bar is None:
            touch_bar = i
        elif not touched:
            # Price moved away — reset the episode
            touch_bar = None

    return drain_bars

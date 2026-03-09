"""
Realized volatility estimators.

Provides multiple estimators with different bias/efficiency trade-offs:
  - Close-to-close (simplest, most common)
  - Parkinson (uses high-low, ~5x more efficient)
  - Garman-Klass (uses OHLC, ~8x more efficient)
  - Yang-Zhang (open-aware, handles overnight jumps)

All estimators output annualized volatility in decimal form (e.g., 0.12 = 12%).

Simplifying assumptions:
  C1. Bars are equally spaced (no gap adjustment for weekends/holidays).
  C2. Annualization factor is passed in; default 252 trading days.
  C3. Volume-weighted variants are not implemented (OHLCV only).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.simulator.types import SimBar


@dataclass
class VolatilityEstimate:
    """Result of a volatility estimation."""

    estimator: str
    annualized_vol: float
    daily_vol: float
    n_bars: int
    window_bars: int
    # Rolling series: one value per output bar
    rolling: list[float] = field(default_factory=list)


def close_to_close(
    bars: list[SimBar],
    window: int = 20,
    annualize: float = 252.0,
) -> VolatilityEstimate:
    """
    Standard close-to-close realized volatility.

    σ = std(log returns) × √(annualize)

    Most common estimator. Unbiased but statistically inefficient —
    ignores intrabar price information.
    """
    if len(bars) < window + 1:
        return VolatilityEstimate(
            estimator="close_to_close",
            annualized_vol=0.0,
            daily_vol=0.0,
            n_bars=len(bars),
            window_bars=window,
        )

    closes = [float(b.close) for b in bars]
    log_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]

    rolling = _rolling_std(log_returns, window)
    annualized = [r * math.sqrt(annualize) for r in rolling]

    daily_vol = rolling[-1] if rolling else 0.0
    ann_vol = annualized[-1] if annualized else 0.0

    return VolatilityEstimate(
        estimator="close_to_close",
        annualized_vol=ann_vol,
        daily_vol=daily_vol,
        n_bars=len(bars),
        window_bars=window,
        rolling=annualized,
    )


def parkinson(
    bars: list[SimBar],
    window: int = 20,
    annualize: float = 252.0,
) -> VolatilityEstimate:
    """
    Parkinson (1980) high-low volatility estimator.

    σ² = (1 / 4·ln2) × E[ln(H/L)²]

    ~5.2x more efficient than close-to-close because it uses the
    full intrabar range. Downward-biased when the true high/low
    occurs between bars (discrete sampling).
    """
    if len(bars) < window:
        return VolatilityEstimate(
            estimator="parkinson",
            annualized_vol=0.0,
            daily_vol=0.0,
            n_bars=len(bars),
            window_bars=window,
        )

    hl_sq = []
    for b in bars:
        h, l = float(b.high), float(b.low)
        if h > 0 and l > 0 and h >= l:
            hl_sq.append(math.log(h / l) ** 2)
        else:
            hl_sq.append(0.0)

    factor = 1.0 / (4.0 * math.log(2.0))
    rolling = []
    for i in range(window - 1, len(hl_sq)):
        chunk = hl_sq[i - window + 1 : i + 1]
        var = factor * sum(chunk) / len(chunk)
        rolling.append(math.sqrt(var))

    annualized = [r * math.sqrt(annualize) for r in rolling]
    daily_vol = rolling[-1] if rolling else 0.0
    ann_vol = annualized[-1] if annualized else 0.0

    return VolatilityEstimate(
        estimator="parkinson",
        annualized_vol=ann_vol,
        daily_vol=daily_vol,
        n_bars=len(bars),
        window_bars=window,
        rolling=annualized,
    )


def garman_klass(
    bars: list[SimBar],
    window: int = 20,
    annualize: float = 252.0,
) -> VolatilityEstimate:
    """
    Garman-Klass (1980) OHLC volatility estimator.

    σ² = 0.5·ln(H/L)² − (2·ln2−1)·ln(C/O)²

    ~7.4x more efficient than close-to-close. Uses open, high, low,
    close. Assumes no drift and continuous trading (biased for gapped
    markets).
    """
    if len(bars) < window:
        return VolatilityEstimate(
            estimator="garman_klass",
            annualized_vol=0.0,
            daily_vol=0.0,
            n_bars=len(bars),
            window_bars=window,
        )

    gk_vals = []
    for b in bars:
        o, h, l, c = float(b.open), float(b.high), float(b.low), float(b.close)
        if o > 0 and h > 0 and l > 0 and c > 0 and h >= l:
            hl = math.log(h / l) ** 2
            co = math.log(c / o) ** 2
            gk_vals.append(0.5 * hl - (2.0 * math.log(2.0) - 1.0) * co)
        else:
            gk_vals.append(0.0)

    rolling = []
    for i in range(window - 1, len(gk_vals)):
        chunk = gk_vals[i - window + 1 : i + 1]
        var = sum(chunk) / len(chunk)
        rolling.append(math.sqrt(max(0.0, var)))

    annualized = [r * math.sqrt(annualize) for r in rolling]
    daily_vol = rolling[-1] if rolling else 0.0
    ann_vol = annualized[-1] if annualized else 0.0

    return VolatilityEstimate(
        estimator="garman_klass",
        annualized_vol=ann_vol,
        daily_vol=daily_vol,
        n_bars=len(bars),
        window_bars=window,
        rolling=annualized,
    )


def yang_zhang(
    bars: list[SimBar],
    window: int = 20,
    annualize: float = 252.0,
) -> VolatilityEstimate:
    """
    Yang-Zhang (2000) volatility estimator.

    Combines overnight (close-to-open), open-to-close, and Rogers-Satchell
    components. Handles overnight jumps and is the minimum-variance unbiased
    estimator for processes with both drift and jumps.

    σ²_yz = σ²_overnight + k·σ²_close_to_close + (1−k)·σ²_rogers_satchell

    where k = 0.34 / (1.34 + (n+1)/(n−1)) and n = window size.
    """
    if len(bars) < window + 1:
        return VolatilityEstimate(
            estimator="yang_zhang",
            annualized_vol=0.0,
            daily_vol=0.0,
            n_bars=len(bars),
            window_bars=window,
        )

    # We need previous close → current open for overnight component
    overnight = []
    open_close = []
    rs_vals = []
    for i in range(1, len(bars)):
        prev_c = float(bars[i - 1].close)
        o = float(bars[i].open)
        h = float(bars[i].high)
        l = float(bars[i].low)
        c = float(bars[i].close)

        if prev_c > 0 and o > 0 and h > 0 and l > 0 and c > 0 and h >= l:
            overnight.append(math.log(o / prev_c))
            open_close.append(math.log(c / o))
            # Rogers-Satchell
            rs = (
                math.log(h / c) * math.log(h / o)
                + math.log(l / c) * math.log(l / o)
            )
            rs_vals.append(rs)
        else:
            overnight.append(0.0)
            open_close.append(0.0)
            rs_vals.append(0.0)

    k = 0.34 / (1.34 + (window + 1) / (window - 1)) if window > 1 else 0.34

    rolling = []
    for i in range(window - 1, len(overnight)):
        on_chunk = overnight[i - window + 1 : i + 1]
        oc_chunk = open_close[i - window + 1 : i + 1]
        rs_chunk = rs_vals[i - window + 1 : i + 1]

        on_mean = sum(on_chunk) / len(on_chunk)
        oc_mean = sum(oc_chunk) / len(oc_chunk)

        on_var = sum((x - on_mean) ** 2 for x in on_chunk) / (len(on_chunk) - 1)
        oc_var = sum((x - oc_mean) ** 2 for x in oc_chunk) / (len(oc_chunk) - 1)
        rs_var = sum(rs_chunk) / len(rs_chunk)

        yz_var = on_var + k * oc_var + (1 - k) * rs_var
        rolling.append(math.sqrt(max(0.0, yz_var)))

    annualized = [r * math.sqrt(annualize) for r in rolling]
    daily_vol = rolling[-1] if rolling else 0.0
    ann_vol = annualized[-1] if annualized else 0.0

    return VolatilityEstimate(
        estimator="yang_zhang",
        annualized_vol=ann_vol,
        daily_vol=daily_vol,
        n_bars=len(bars),
        window_bars=window,
        rolling=annualized,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rolling_std(values: list[float], window: int) -> list[float]:
    """Rolling sample standard deviation."""
    result = []
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1 : i + 1]
        mean = sum(chunk) / len(chunk)
        var = sum((x - mean) ** 2 for x in chunk) / (len(chunk) - 1)
        result.append(math.sqrt(var))
    return result

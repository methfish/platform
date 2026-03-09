"""
Order Flow Imbalance (OFI) predictive-power analysis.

Estimates how well order flow imbalance predicts future price moves
using OHLCV bar proxies. Since we don't have tick-level order book
data, we use bar-level proxies for OFI:

  OFI_proxy = signed_volume × bar_direction

  where:
    bar_direction = sign(close − open)
    signed_volume = volume × bar_direction

We then measure the correlation and R² between OFI and future returns
at various horizons. High R² suggests that the simulator should model
OFI-driven fills; low R² validates the simulator's assumption that
fill order doesn't matter much (assumption A2: no market impact).

Simplifying assumptions:
  C10. OFI proxy from OHLCV only (no Level 2 or tick data).
  C11. Volume is treated as total volume (no buy/sell breakdown).
  C12. Bar direction (close > open) is the only signed volume proxy.
  C13. Predictive power is measured via simple linear regression R².
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.simulator.types import SimBar


@dataclass
class OFIHorizonResult:
    """OFI predictive power at a single forward horizon."""

    horizon_bars: int
    correlation: float       # Pearson correlation OFI vs future return
    r_squared: float         # R² of simple linear regression
    slope: float             # Regression slope (return per unit OFI)
    n_observations: int
    mean_ofi: float = 0.0
    std_ofi: float = 0.0
    mean_return_bps: float = 0.0


@dataclass
class OFIProfile:
    """OFI predictive-power analysis across horizons."""

    symbol: str
    n_bars: int
    ofi_window: int
    horizons: list[OFIHorizonResult] = field(default_factory=list)
    # Summary
    max_r_squared: float = 0.0
    best_horizon: int = 0
    # Verdict: does OFI matter for this symbol?
    ofi_is_predictive: bool = False


def analyze_ofi(
    bars: list[SimBar],
    ofi_window: int = 5,
    horizons: Optional[list[int]] = None,
    r_squared_threshold: float = 0.02,
    symbol: str = "",
) -> OFIProfile:
    """
    Analyze the predictive power of OFI for future price moves.

    Steps:
      1. Compute bar-level OFI proxy (signed volume).
      2. Aggregate OFI over a rolling window.
      3. For each forward horizon, regress future returns on OFI.
      4. Report correlation, R², and slope.

    Args:
        bars: Historical OHLCV bars.
        ofi_window: Rolling window for OFI aggregation (bars).
        horizons: Forward horizons to test. Default [1, 2, 5, 10].
        r_squared_threshold: R² above this → OFI is "predictive".
        symbol: Symbol name for labeling.
    """
    if horizons is None:
        horizons = [1, 2, 5, 10]

    if len(bars) < ofi_window + max(horizons, default=0) + 1:
        return OFIProfile(symbol=symbol, n_bars=len(bars), ofi_window=ofi_window)

    # Step 1: bar-level OFI proxy
    bar_ofi = []
    for b in bars:
        o, c, v = float(b.open), float(b.close), float(b.volume)
        if o > 0:
            direction = 1.0 if c >= o else -1.0
            bar_ofi.append(direction * v)
        else:
            bar_ofi.append(0.0)

    # Step 2: rolling OFI
    rolling_ofi = []
    for i in range(ofi_window - 1, len(bar_ofi)):
        rolling_ofi.append(sum(bar_ofi[i - ofi_window + 1 : i + 1]))

    # Align indices: rolling_ofi[j] corresponds to bars[j + ofi_window - 1]
    base_idx = ofi_window - 1

    # Precompute mid prices for returns
    mids = [float((b.high + b.low + b.close)) / 3.0 for b in bars]

    horizon_results = []
    max_r2 = 0.0
    best_h = 0

    for h in horizons:
        ofi_vals: list[float] = []
        ret_vals: list[float] = []

        for j in range(len(rolling_ofi)):
            bar_i = base_idx + j
            future_i = bar_i + h
            if future_i >= len(bars):
                break

            mid_now = mids[bar_i]
            mid_future = mids[future_i]
            if mid_now > 0 and mid_future > 0:
                ret_bps = (mid_future - mid_now) / mid_now * 10000.0
                ofi_vals.append(rolling_ofi[j])
                ret_vals.append(ret_bps)

        if len(ofi_vals) < 10:
            horizon_results.append(OFIHorizonResult(
                horizon_bars=h, correlation=0.0, r_squared=0.0,
                slope=0.0, n_observations=len(ofi_vals),
            ))
            continue

        # Simple linear regression: ret = slope × ofi + intercept
        corr = _pearson(ofi_vals, ret_vals)
        slope, _ = _linear_regression(ofi_vals, ret_vals)
        r2 = corr ** 2

        mean_ofi = sum(ofi_vals) / len(ofi_vals)
        std_ofi = _std(ofi_vals)
        mean_ret = sum(ret_vals) / len(ret_vals)

        result = OFIHorizonResult(
            horizon_bars=h,
            correlation=corr,
            r_squared=r2,
            slope=slope,
            n_observations=len(ofi_vals),
            mean_ofi=mean_ofi,
            std_ofi=std_ofi,
            mean_return_bps=mean_ret,
        )
        horizon_results.append(result)

        if r2 > max_r2:
            max_r2 = r2
            best_h = h

    return OFIProfile(
        symbol=symbol,
        n_bars=len(bars),
        ofi_window=ofi_window,
        horizons=horizon_results,
        max_r_squared=max_r2,
        best_horizon=best_h,
        ofi_is_predictive=max_r2 > r_squared_threshold,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def _linear_regression(
    x: list[float], y: list[float],
) -> tuple[float, float]:
    """Simple OLS: returns (slope, intercept)."""
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    mx = sum(x) / n
    my = sum(y) / n
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    if ss_xx == 0:
        return 0.0, my
    slope = ss_xy / ss_xx
    intercept = my - slope * mx
    return slope, intercept


def _std(values: list[float]) -> float:
    """Sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)

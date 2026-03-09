"""
Walk-forward calibration routine.

Calibrates simulator parameters using a rolling-window approach to
avoid look-ahead bias:

  |--- train window ---|--- test window ---|
                       |--- train window ---|--- test window ---|
                                            |--- train window ---|...

For each window:
  1. Run all estimators on the train window.
  2. Produce a CalibrationSnapshot.
  3. Optionally validate on the test window (out-of-sample check).

The final output is the calibration from the most recent train window,
plus stability metrics (how much parameters change across windows).

Simplifying assumptions:
  C18. Walk-forward windows are bar-count-based, not time-based
       (avoids complexity with weekends/holidays).
  C19. All estimators run on the same train window (no per-estimator
       window tuning).
  C20. Stability is measured as coefficient of variation across windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from app.simulator.calibration.adverse_selection import (
    AdverseSelectionProfile,
    estimate_adverse_selection,
    recommended_slippage_bps,
)
from app.simulator.calibration.fill_probability import (
    FillProbProfile,
    estimate_fill_probability,
    recommended_spread_bps,
)
from app.simulator.calibration.ofi import OFIProfile, analyze_ofi
from app.simulator.calibration.parameter_store import (
    CalibratedParam,
    CalibrationSnapshot,
    ParameterStore,
)
from app.simulator.calibration.queue_model import (
    QueueProfile,
    estimate_queue_depletion,
)
from app.simulator.calibration.volatility import (
    VolatilityEstimate,
    close_to_close,
    garman_klass,
    parkinson,
    yang_zhang,
)
from app.simulator.types import SimBar


@dataclass
class WindowResult:
    """Calibration result from a single walk-forward window."""

    window_idx: int
    train_start_bar: int
    train_end_bar: int
    test_start_bar: int
    test_end_bar: int
    snapshot: CalibrationSnapshot


@dataclass
class StabilityMetric:
    """How stable a parameter is across walk-forward windows."""

    param_name: str
    values: list[float] = field(default_factory=list)
    mean: float = 0.0
    std: float = 0.0
    cv: float = 0.0         # Coefficient of variation (std/mean)
    is_stable: bool = True   # CV < threshold


@dataclass
class WalkForwardResult:
    """Complete walk-forward calibration output."""

    symbol: str
    n_bars: int
    n_windows: int
    train_size: int
    test_size: int
    step_size: int
    windows: list[WindowResult] = field(default_factory=list)
    stability: list[StabilityMetric] = field(default_factory=list)
    # The final calibration (from the most recent window)
    final_snapshot: Optional[CalibrationSnapshot] = None


def walk_forward_calibrate(
    bars: list[SimBar],
    train_size: int = 500,
    test_size: int = 100,
    step_size: int = 100,
    vol_window: int = 20,
    fill_max_distance_bps: float = 20.0,
    adverse_distance_bps: float = 3.0,
    ofi_window: int = 5,
    stability_cv_threshold: float = 0.30,
    symbol: str = "",
    store: Optional[ParameterStore] = None,
) -> WalkForwardResult:
    """
    Run walk-forward calibration across all estimators.

    Args:
        bars: Full historical bar dataset.
        train_size: Number of bars per training window.
        test_size: Number of bars per test window (for validation).
        step_size: How many bars to advance between windows.
        vol_window: Window for volatility estimators.
        fill_max_distance_bps: Max distance for fill probability analysis.
        adverse_distance_bps: Limit distance for adverse selection.
        ofi_window: Rolling window for OFI calculation.
        stability_cv_threshold: CV above this → parameter is "unstable".
        symbol: Symbol name.
        store: Optional ParameterStore to persist the final result.

    Returns:
        WalkForwardResult with per-window calibrations and stability metrics.
    """
    n_bars = len(bars)
    min_required = train_size + test_size
    if n_bars < min_required:
        return WalkForwardResult(
            symbol=symbol, n_bars=n_bars, n_windows=0,
            train_size=train_size, test_size=test_size, step_size=step_size,
        )

    windows: list[WindowResult] = []
    window_idx = 0
    start = 0

    while start + train_size + test_size <= n_bars:
        train_end = start + train_size
        test_end = train_end + test_size

        train_bars = bars[start:train_end]
        # test_bars = bars[train_end:test_end]  # Reserved for OOS validation

        snapshot = _calibrate_window(
            train_bars,
            vol_window=vol_window,
            fill_max_distance_bps=fill_max_distance_bps,
            adverse_distance_bps=adverse_distance_bps,
            ofi_window=ofi_window,
            symbol=symbol,
        )

        windows.append(WindowResult(
            window_idx=window_idx,
            train_start_bar=start,
            train_end_bar=train_end,
            test_start_bar=train_end,
            test_end_bar=test_end,
            snapshot=snapshot,
        ))

        window_idx += 1
        start += step_size

    # Also calibrate on the final window (most recent data)
    final_train = bars[max(0, n_bars - train_size) :]
    final_snapshot = _calibrate_window(
        final_train,
        vol_window=vol_window,
        fill_max_distance_bps=fill_max_distance_bps,
        adverse_distance_bps=adverse_distance_bps,
        ofi_window=ofi_window,
        symbol=symbol,
    )
    final_snapshot.calibrated_at = datetime.now(timezone.utc).isoformat()
    if bars:
        final_snapshot.data_start = bars[0].timestamp.isoformat()
        final_snapshot.data_end = bars[-1].timestamp.isoformat()

    # Compute stability metrics
    stability = _compute_stability(windows, stability_cv_threshold)

    # Annotate final snapshot parameters with confidence from stability
    _annotate_confidence(final_snapshot, stability)

    # Persist if store provided
    if store is not None:
        store.save(final_snapshot)

    return WalkForwardResult(
        symbol=symbol,
        n_bars=n_bars,
        n_windows=len(windows),
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
        windows=windows,
        stability=stability,
        final_snapshot=final_snapshot,
    )


# ---------------------------------------------------------------------------
# Single-window calibration
# ---------------------------------------------------------------------------


def _calibrate_window(
    bars: list[SimBar],
    vol_window: int,
    fill_max_distance_bps: float,
    adverse_distance_bps: float,
    ofi_window: int,
    symbol: str,
) -> CalibrationSnapshot:
    """Run all estimators on a single window and produce a snapshot."""

    params: list[CalibratedParam] = []
    summaries: dict[str, Any] = {}

    # 1. Volatility
    vol_cc = close_to_close(bars, window=vol_window)
    vol_pk = parkinson(bars, window=vol_window)
    vol_gk = garman_klass(bars, window=vol_window)
    vol_yz = yang_zhang(bars, window=vol_window)

    # Use Garman-Klass as primary (best efficiency for OHLC data)
    params.append(CalibratedParam(
        name="realized_vol_annualized",
        value=vol_gk.annualized_vol,
        unit="decimal",
        source="garman_klass",
        n_observations=vol_gk.n_bars,
    ))

    summaries["volatility"] = {
        "close_to_close": vol_cc.annualized_vol,
        "parkinson": vol_pk.annualized_vol,
        "garman_klass": vol_gk.annualized_vol,
        "yang_zhang": vol_yz.annualized_vol,
    }

    # 2. Fill probability → spread calibration
    fill_prof = estimate_fill_probability(
        bars, max_distance_bps=fill_max_distance_bps, symbol=symbol,
    )
    rec_spread = recommended_spread_bps(fill_prof, target_fill_pct=0.50)

    if rec_spread is not None:
        params.append(CalibratedParam(
            name="spread_bps",
            value=rec_spread,
            unit="bps",
            source="fill_probability",
            n_observations=fill_prof.n_bars,
        ))

    summaries["fill_probability"] = {
        "buy_half_life_bps": fill_prof.buy_half_life_bps,
        "sell_half_life_bps": fill_prof.sell_half_life_bps,
        "recommended_spread_bps": rec_spread,
    }

    # 3. Adverse selection → slippage calibration
    adverse = estimate_adverse_selection(
        bars, limit_distance_bps=adverse_distance_bps, symbol=symbol,
    )
    rec_slip = recommended_slippage_bps(adverse)
    params.append(CalibratedParam(
        name="slippage_bps",
        value=rec_slip,
        unit="bps",
        source="adverse_selection",
        n_observations=adverse.n_bars,
    ))

    summaries["adverse_selection"] = {
        "mean_buy_adverse_bps": adverse.mean_buy_adverse_bps,
        "mean_sell_adverse_bps": adverse.mean_sell_adverse_bps,
        "recommended_slippage_bps": rec_slip,
        "horizons": [
            {
                "bars": h.horizon_bars,
                "buy_bps": h.buy_adverse_bps,
                "sell_bps": h.sell_adverse_bps,
            }
            for h in adverse.horizons
        ],
    }

    # 4. OFI analysis
    ofi_prof = analyze_ofi(bars, ofi_window=ofi_window, symbol=symbol)
    summaries["ofi"] = {
        "max_r_squared": ofi_prof.max_r_squared,
        "best_horizon": ofi_prof.best_horizon,
        "is_predictive": ofi_prof.ofi_is_predictive,
    }

    # 5. Queue depletion → queue_behind_pct + fill_rate_pct
    queue_prof = estimate_queue_depletion(bars, symbol=symbol)
    params.append(CalibratedParam(
        name="queue_behind_pct",
        value=queue_prof.recommended_queue_behind_pct,
        unit="pct",
        source="queue_depletion",
        n_observations=queue_prof.n_bars,
    ))
    params.append(CalibratedParam(
        name="fill_rate_pct",
        value=queue_prof.recommended_fill_rate_pct,
        unit="pct",
        source="queue_depletion",
        n_observations=queue_prof.n_bars,
    ))

    summaries["queue_depletion"] = {
        "recommended_queue_behind_pct": queue_prof.recommended_queue_behind_pct,
        "recommended_fill_rate_pct": queue_prof.recommended_fill_rate_pct,
        "estimates": [
            {
                "distance_bps": e.distance_bps,
                "mean_drain_bars": e.mean_drain_bars,
                "n_episodes": e.n_episodes,
                "immediate_pct": e.n_immediate / e.n_episodes if e.n_episodes > 0 else 0,
            }
            for e in queue_prof.estimates
        ],
    }

    return CalibrationSnapshot(
        symbol=symbol,
        n_bars=len(bars),
        interval=bars[0].interval if bars else "",
        parameters=params,
        estimator_summaries=summaries,
    )


# ---------------------------------------------------------------------------
# Stability analysis
# ---------------------------------------------------------------------------


def _compute_stability(
    windows: list[WindowResult],
    cv_threshold: float,
) -> list[StabilityMetric]:
    """Compute parameter stability across walk-forward windows."""
    if not windows:
        return []

    # Collect all parameter names
    param_names: set[str] = set()
    for w in windows:
        for p in w.snapshot.parameters:
            param_names.add(p.name)

    metrics = []
    for name in sorted(param_names):
        values = []
        for w in windows:
            p = w.snapshot.get_param(name)
            if p is not None:
                values.append(p.value)

        if not values:
            continue

        mean = sum(values) / len(values)
        if len(values) > 1:
            std = math.sqrt(
                sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            )
        else:
            std = 0.0

        cv = std / abs(mean) if abs(mean) > 1e-10 else 0.0

        metrics.append(StabilityMetric(
            param_name=name,
            values=values,
            mean=mean,
            std=std,
            cv=cv,
            is_stable=cv < cv_threshold,
        ))

    return metrics


def _annotate_confidence(
    snapshot: CalibrationSnapshot,
    stability: list[StabilityMetric],
) -> None:
    """Set confidence scores on snapshot parameters based on stability."""
    stability_map = {s.param_name: s for s in stability}

    for p in snapshot.parameters:
        s = stability_map.get(p.name)
        if s is None:
            # No stability data → moderate confidence based on observations
            p.confidence = min(1.0, p.n_observations / 500.0) * 0.5
            continue

        # Confidence = f(stability, observations)
        # Stable + many observations → high confidence
        stability_score = max(0.0, 1.0 - s.cv) if s.cv < 1.0 else 0.1
        obs_score = min(1.0, p.n_observations / 500.0)
        p.confidence = stability_score * 0.6 + obs_score * 0.4

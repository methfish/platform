"""
Unit tests for the simulator calibration package.

Tests each estimator independently and the walk-forward routine end-to-end.
"""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.simulator.types import SimBar

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

T0 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)


def _bars(n: int = 100, base: float = 1.1000, vol: float = 0.001) -> list[SimBar]:
    """Generate synthetic bars with controlled volatility."""
    import random
    random.seed(123)
    bars = []
    price = base
    for i in range(n):
        ret = random.gauss(0, vol)
        new_price = price * math.exp(ret)
        noise = abs(ret) * price * 0.5 + 0.00005
        h = max(price, new_price) + abs(random.gauss(0, noise))
        l = min(price, new_price) - abs(random.gauss(0, noise))
        l = max(l, price * 0.95)
        bars.append(SimBar(
            timestamp=T0 + timedelta(hours=i),
            open=Decimal(str(round(price, 5))),
            high=Decimal(str(round(h, 5))),
            low=Decimal(str(round(l, 5))),
            close=Decimal(str(round(new_price, 5))),
            volume=Decimal("1000000"),
            symbol="EURUSD",
            interval="1h",
        ))
        price = new_price
    return bars


# ====================================================================
# Volatility Estimators
# ====================================================================


class TestVolatility:

    def test_close_to_close_returns_positive(self):
        from app.simulator.calibration.volatility import close_to_close
        bars = _bars(50)
        result = close_to_close(bars, window=10)
        assert result.annualized_vol > 0
        assert result.daily_vol > 0
        assert result.estimator == "close_to_close"

    def test_parkinson_returns_positive(self):
        from app.simulator.calibration.volatility import parkinson
        bars = _bars(50)
        result = parkinson(bars, window=10)
        assert result.annualized_vol > 0
        assert result.estimator == "parkinson"

    def test_garman_klass_returns_positive(self):
        from app.simulator.calibration.volatility import garman_klass
        bars = _bars(50)
        result = garman_klass(bars, window=10)
        assert result.annualized_vol > 0
        assert result.estimator == "garman_klass"

    def test_yang_zhang_returns_positive(self):
        from app.simulator.calibration.volatility import yang_zhang
        bars = _bars(50)
        result = yang_zhang(bars, window=10)
        assert result.annualized_vol > 0
        assert result.estimator == "yang_zhang"

    def test_rolling_series_length(self):
        from app.simulator.calibration.volatility import close_to_close
        bars = _bars(50)
        result = close_to_close(bars, window=10)
        # Rolling series: n_returns = 49, rolling of window 10 → 40 values
        assert len(result.rolling) == 40

    def test_insufficient_data_returns_zero(self):
        from app.simulator.calibration.volatility import close_to_close
        bars = _bars(5)
        result = close_to_close(bars, window=20)
        assert result.annualized_vol == 0.0

    def test_estimator_ordering(self):
        """Parkinson should be ≤ close-to-close (known theoretical property
        for continuous processes — Parkinson has lower variance but can be
        biased differently). We just check they're in the same ballpark."""
        from app.simulator.calibration.volatility import close_to_close, parkinson
        bars = _bars(200, vol=0.005)
        cc = close_to_close(bars, window=50)
        pk = parkinson(bars, window=50)
        # Both should be within 3x of each other
        ratio = cc.annualized_vol / pk.annualized_vol if pk.annualized_vol > 0 else 0
        assert 0.3 < ratio < 3.0


# ====================================================================
# Fill Probability
# ====================================================================


class TestFillProbability:

    def test_fill_prob_decreases_with_distance(self):
        from app.simulator.calibration.fill_probability import estimate_fill_probability
        bars = _bars(200)
        profile = estimate_fill_probability(bars, max_distance_bps=10.0, step_bps=1.0)
        assert len(profile.buckets) > 0
        # Fill probability should generally decrease with distance
        probs = [b.buy_fill_prob for b in profile.buckets]
        # First bucket should have higher prob than last
        assert probs[0] >= probs[-1]

    def test_zero_distance_high_fill_prob(self):
        """At very small distance, most bars should trade through."""
        from app.simulator.calibration.fill_probability import estimate_fill_probability
        bars = _bars(200, vol=0.005)
        profile = estimate_fill_probability(bars, max_distance_bps=20.0, step_bps=0.5)
        # At 0.5 bps from mid, fill prob should be high
        assert profile.buckets[0].buy_fill_prob > 0.3

    def test_recommended_spread(self):
        from app.simulator.calibration.fill_probability import (
            estimate_fill_probability,
            recommended_spread_bps,
        )
        bars = _bars(200, vol=0.005)
        profile = estimate_fill_probability(bars, max_distance_bps=20.0)
        spread = recommended_spread_bps(profile, target_fill_pct=0.50)
        # Should return a reasonable value or None
        if spread is not None:
            assert 0 < spread <= 20.0

    def test_empty_bars(self):
        from app.simulator.calibration.fill_probability import estimate_fill_probability
        profile = estimate_fill_probability([], symbol="EURUSD")
        assert profile.n_bars == 0
        assert len(profile.buckets) == 0


# ====================================================================
# Adverse Selection
# ====================================================================


class TestAdverseSelection:

    def test_returns_horizons(self):
        from app.simulator.calibration.adverse_selection import estimate_adverse_selection
        bars = _bars(200)
        profile = estimate_adverse_selection(bars, horizons=[1, 5, 10])
        assert len(profile.horizons) == 3
        assert profile.horizons[0].horizon_bars == 1
        assert profile.horizons[1].horizon_bars == 5

    def test_has_observations(self):
        from app.simulator.calibration.adverse_selection import estimate_adverse_selection
        bars = _bars(200, vol=0.005)
        profile = estimate_adverse_selection(bars, limit_distance_bps=5.0)
        # Should have some fill observations
        for h in profile.horizons:
            assert h.buy_n > 0 or h.sell_n > 0

    def test_recommended_slippage(self):
        from app.simulator.calibration.adverse_selection import (
            estimate_adverse_selection,
            recommended_slippage_bps,
        )
        bars = _bars(200, vol=0.005)
        profile = estimate_adverse_selection(bars)
        slip = recommended_slippage_bps(profile)
        assert slip >= 0  # Can be zero for low-vol data

    def test_insufficient_data(self):
        from app.simulator.calibration.adverse_selection import estimate_adverse_selection
        bars = _bars(3)
        profile = estimate_adverse_selection(bars, horizons=[1, 5, 10])
        assert len(profile.horizons) == 0


# ====================================================================
# OFI Analysis
# ====================================================================


class TestOFI:

    def test_returns_horizons(self):
        from app.simulator.calibration.ofi import analyze_ofi
        bars = _bars(200)
        profile = analyze_ofi(bars, ofi_window=5, horizons=[1, 5])
        assert len(profile.horizons) == 2
        assert profile.horizons[0].horizon_bars == 1

    def test_r_squared_bounded(self):
        from app.simulator.calibration.ofi import analyze_ofi
        bars = _bars(200)
        profile = analyze_ofi(bars)
        for h in profile.horizons:
            assert 0 <= h.r_squared <= 1.0

    def test_correlation_bounded(self):
        from app.simulator.calibration.ofi import analyze_ofi
        bars = _bars(200)
        profile = analyze_ofi(bars)
        for h in profile.horizons:
            assert -1.0 <= h.correlation <= 1.0

    def test_insufficient_data(self):
        from app.simulator.calibration.ofi import analyze_ofi
        bars = _bars(3)
        profile = analyze_ofi(bars, ofi_window=5)
        assert len(profile.horizons) == 0


# ====================================================================
# Queue Depletion
# ====================================================================


class TestQueueDepletion:

    def test_returns_estimates(self):
        from app.simulator.calibration.queue_model import estimate_queue_depletion
        bars = _bars(200, vol=0.005)
        profile = estimate_queue_depletion(bars, distances_bps=[2.0, 5.0, 10.0])
        assert len(profile.estimates) == 3

    def test_recommended_params_bounded(self):
        from app.simulator.calibration.queue_model import estimate_queue_depletion
        bars = _bars(200, vol=0.005)
        profile = estimate_queue_depletion(bars)
        assert 0 <= profile.recommended_queue_behind_pct <= 1.0
        assert 0 < profile.recommended_fill_rate_pct <= 10.0

    def test_mean_drain_non_negative(self):
        from app.simulator.calibration.queue_model import estimate_queue_depletion
        bars = _bars(200)
        profile = estimate_queue_depletion(bars)
        for e in profile.estimates:
            assert e.mean_drain_bars >= 0

    def test_insufficient_data(self):
        from app.simulator.calibration.queue_model import estimate_queue_depletion
        bars = _bars(3)
        profile = estimate_queue_depletion(bars)
        # Should return defaults
        assert profile.recommended_queue_behind_pct == 0.50


# ====================================================================
# Parameter Store
# ====================================================================


class TestParameterStore:

    def test_save_and_load(self):
        from app.simulator.calibration.parameter_store import (
            CalibratedParam,
            CalibrationSnapshot,
            ParameterStore,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParameterStore(base_dir=tmpdir)

            snapshot = CalibrationSnapshot(
                symbol="EURUSD",
                calibrated_at="2025-01-15T10:30:00+00:00",
                n_bars=500,
                parameters=[
                    CalibratedParam(
                        name="spread_bps", value=5.0, unit="bps",
                        source="fill_probability", confidence=0.8,
                    ),
                ],
            )
            path = store.save(snapshot)
            assert path.exists()

            loaded = store.load_latest("EURUSD")
            assert loaded is not None
            assert loaded.symbol == "EURUSD"
            assert len(loaded.parameters) == 1
            assert loaded.parameters[0].name == "spread_bps"
            assert loaded.parameters[0].value == 5.0

    def test_list_snapshots(self):
        from app.simulator.calibration.parameter_store import (
            CalibrationSnapshot,
            ParameterStore,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParameterStore(base_dir=tmpdir)

            for ts in ["2025-01-10T10:00:00", "2025-01-11T10:00:00"]:
                store.save(CalibrationSnapshot(
                    symbol="EURUSD", calibrated_at=ts, n_bars=100,
                ))

            snaps = store.list_snapshots("EURUSD")
            assert len(snaps) == 2

    def test_to_config_overrides(self):
        from app.simulator.calibration.parameter_store import (
            CalibratedParam,
            CalibrationSnapshot,
        )
        snapshot = CalibrationSnapshot(
            symbol="EURUSD",
            parameters=[
                CalibratedParam(name="spread_bps", value=7.5, unit="bps", source="test"),
                CalibratedParam(name="slippage_bps", value=1.2, unit="bps", source="test"),
                CalibratedParam(name="queue_behind_pct", value=0.35, unit="pct", source="test"),
            ],
        )
        overrides = snapshot.to_config_overrides()
        assert overrides["spread_bps"] == Decimal("7.5")
        assert overrides["slippage_bps"] == Decimal("1.2")
        assert overrides["queue_behind_pct"] == Decimal("0.35")

    def test_load_nonexistent_returns_none(self):
        from app.simulator.calibration.parameter_store import ParameterStore
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParameterStore(base_dir=tmpdir)
            assert store.load_latest("NOSYMBOL") is None


# ====================================================================
# Walk-Forward Calibration (end-to-end)
# ====================================================================


class TestWalkForwardCalibration:

    def test_end_to_end(self):
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        result = walk_forward_calibrate(
            bars=bars,
            train_size=300,
            test_size=50,
            step_size=100,
            symbol="EURUSD",
        )
        assert result.n_windows > 0
        assert result.final_snapshot is not None
        assert len(result.final_snapshot.parameters) > 0

    def test_stability_metrics_populated(self):
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        result = walk_forward_calibrate(
            bars=bars,
            train_size=300,
            test_size=50,
            step_size=100,
            symbol="EURUSD",
        )
        assert len(result.stability) > 0
        for s in result.stability:
            assert s.cv >= 0

    def test_report_generation(self):
        from app.simulator.calibration import (
            format_walk_forward_report,
            walk_forward_calibrate,
        )
        bars = _bars(800, vol=0.003)
        result = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
            symbol="EURUSD",
        )
        report = format_walk_forward_report(result)
        assert "WALK-FORWARD CALIBRATION" in report
        assert "EURUSD" in report
        assert "PARAMETER STABILITY" in report

    def test_persists_to_store(self):
        from app.simulator.calibration import ParameterStore, walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ParameterStore(base_dir=tmpdir)
            result = walk_forward_calibrate(
                bars=bars, train_size=300, test_size=50, step_size=100,
                symbol="EURUSD", store=store,
            )
            loaded = store.load_latest("EURUSD")
            assert loaded is not None
            assert loaded.symbol == "EURUSD"

    def test_insufficient_data(self):
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(10)
        result = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
        )
        assert result.n_windows == 0
        assert result.final_snapshot is None

    def test_config_overrides_roundtrip(self):
        """Calibrated params can be applied to SimulatorConfig."""
        from app.simulator.calibration import walk_forward_calibrate
        from app.simulator.types import SimulatorConfig

        bars = _bars(800, vol=0.003)
        result = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
            symbol="EURUSD",
        )
        if result.final_snapshot:
            overrides = result.final_snapshot.to_config_overrides()
            config = SimulatorConfig(**overrides)
            # Should not raise, and symbol should be preserved from defaults
            assert config.symbol == "EURUSD"

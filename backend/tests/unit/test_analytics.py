"""
Unit tests for the simulator analytics package.

Tests each report generator and validates both to_dict() and format() outputs.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.simulator import (
    OrderSide,
    SimBar,
    SimOrderType,
    SimulatorConfig,
    SimulatorEngine,
)
from app.simulator.engine import SimulatorResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

T0 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)


def _bars(n: int = 100, base: float = 1.1000, vol: float = 0.001) -> list[SimBar]:
    random.seed(42)
    bars = []
    price = base
    for i in range(n):
        ret = random.gauss(0, vol)
        new_price = price * math.exp(ret)
        noise = max(abs(ret) * price * 0.5, 0.00005)
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


def _config(**overrides) -> SimulatorConfig:
    defaults = dict(
        initial_capital=Decimal("100000"),
        symbol="EURUSD",
        maker_fee_rate=Decimal("0.00003"),
        taker_fee_rate=Decimal("0.00010"),
        spread_bps=Decimal("10"),
        slippage_bps=Decimal("1"),
        order_latency_ms=0,
        cancel_latency_ms=0,
    )
    defaults.update(overrides)
    return SimulatorConfig(**defaults)


def _run_with_trades(n_bars: int = 200) -> tuple[SimulatorResult, list[SimBar]]:
    """Run a simulation that produces trades."""
    bars = _bars(n_bars, vol=0.002)
    config = _config()

    def strategy(eng: SimulatorEngine, bar: SimBar):
        if "closes" not in eng.state:
            eng.state["closes"] = []
            eng.state["prev"] = None
        eng.state["closes"].append(float(bar.close))
        closes = eng.state["closes"]
        if len(closes) < 15:
            return
        fast = sum(closes[-5:]) / 5
        slow = sum(closes[-15:]) / 15
        signal = "BUY" if fast > slow else "SELL"
        if signal != eng.state["prev"]:
            pos = eng.get_position()
            if pos != 0:
                side = OrderSide.SELL if pos > 0 else OrderSide.BUY
                eng.submit_order(side, abs(pos), SimOrderType.MARKET)
            qty = Decimal("10000")
            eng.submit_order(
                OrderSide.BUY if signal == "BUY" else OrderSide.SELL,
                qty, SimOrderType.MARKET,
            )
            eng.state["prev"] = signal

    engine = SimulatorEngine(config)
    result = engine.run(bars, strategy)
    return result, bars


# ====================================================================
# Backtest Summary
# ====================================================================


class TestBacktestSummary:

    def test_generates_with_trades(self):
        from app.simulator.analytics import generate_backtest_summary
        result, bars = _run_with_trades()
        report = generate_backtest_summary(result, bars)
        assert report.total_trades > 0
        assert report.total_bars > 0
        assert report.initial_capital == 100000.0
        assert report.symbol == "EURUSD"

    def test_to_dict_has_required_keys(self):
        from app.simulator.analytics import generate_backtest_summary
        result, bars = _run_with_trades()
        report = generate_backtest_summary(result, bars)
        d = report.to_dict()
        assert d["report_type"] == "backtest_summary"
        assert "capital" in d
        assert "risk" in d
        assert "trades" in d
        assert "execution" in d

    def test_format_returns_string(self):
        from app.simulator.analytics import generate_backtest_summary
        result, bars = _run_with_trades()
        report = generate_backtest_summary(result, bars)
        text = report.format()
        assert "BACKTEST SUMMARY" in text
        assert "Sharpe" in text

    def test_json_serializable(self):
        from app.simulator.analytics import generate_backtest_summary
        result, bars = _run_with_trades()
        report = generate_backtest_summary(result, bars)
        s = json.dumps(report.to_dict(), default=str)
        assert len(s) > 100

    def test_empty_result(self):
        from app.simulator.analytics import generate_backtest_summary
        result = SimulatorResult(config=_config())
        report = generate_backtest_summary(result)
        assert report.total_trades == 0

    def test_sharpe_and_sortino(self):
        from app.simulator.analytics import generate_backtest_summary
        result, bars = _run_with_trades()
        report = generate_backtest_summary(result, bars)
        # Sharpe and Sortino should be finite
        assert math.isfinite(report.sharpe_ratio)
        assert report.sortino_ratio >= 0 or math.isfinite(report.sortino_ratio)


# ====================================================================
# PnL Attribution
# ====================================================================


class TestPnLAttribution:

    def test_generates_with_trades(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        report = generate_pnl_attribution(result)
        assert report.total_net_pnl != 0 or report.total_alpha != 0

    def test_alpha_minus_costs_equals_net(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        report = generate_pnl_attribution(result)
        # Net ≈ gross − commission (rough check)
        assert abs(report.total_net_pnl - report.total_gross_pnl) < abs(report.total_commission_cost) + 1

    def test_cumulative_series_length(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        report = generate_pnl_attribution(result)
        assert len(report.cumulative_net) == len(result.trades)

    def test_to_dict_structure(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        d = generate_pnl_attribution(result).to_dict()
        assert d["report_type"] == "pnl_attribution"
        assert "totals" in d
        assert "by_side" in d
        assert "cumulative" in d

    def test_format_readable(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        text = generate_pnl_attribution(result).format()
        assert "PNL ATTRIBUTION" in text
        assert "Alpha" in text

    def test_long_short_split(self):
        from app.simulator.analytics import generate_pnl_attribution
        result, _ = _run_with_trades()
        report = generate_pnl_attribution(result)
        total_from_sides = 0
        if report.long_bucket:
            total_from_sides += report.long_bucket.n_trades
        if report.short_bucket:
            total_from_sides += report.short_bucket.n_trades
        assert total_from_sides == len(result.trades)


# ====================================================================
# Fill Toxicity
# ====================================================================


class TestFillToxicity:

    def test_generates_with_trades(self):
        from app.simulator.analytics import generate_fill_toxicity
        result, bars = _run_with_trades()
        report = generate_fill_toxicity(result, bars)
        assert report.overall_pct_adverse >= 0

    def test_toxicity_score_bounded(self):
        from app.simulator.analytics import generate_fill_toxicity
        result, bars = _run_with_trades()
        report = generate_fill_toxicity(result, bars)
        assert 0 <= report.overall_toxicity_score <= 1.0

    def test_to_dict_structure(self):
        from app.simulator.analytics import generate_fill_toxicity
        result, bars = _run_with_trades()
        d = generate_fill_toxicity(result, bars).to_dict()
        assert d["report_type"] == "fill_toxicity"
        assert "overall" in d
        assert "by_fill_type" in d

    def test_format_readable(self):
        from app.simulator.analytics import generate_fill_toxicity
        result, bars = _run_with_trades()
        text = generate_fill_toxicity(result, bars).format()
        assert "FILL TOXICITY" in text

    def test_empty_result(self):
        from app.simulator.analytics import generate_fill_toxicity
        result = SimulatorResult(config=_config())
        report = generate_fill_toxicity(result, [])
        assert report.overall_mean_adverse_bps == 0.0


# ====================================================================
# Inventory Behavior
# ====================================================================


class TestInventoryBehavior:

    def test_generates_with_trades(self):
        from app.simulator.analytics import generate_inventory_behavior
        result, bars = _run_with_trades()
        report = generate_inventory_behavior(result, bars)
        assert report.max_long_position > 0 or report.max_short_position < 0

    def test_time_percentages_sum_to_100(self):
        from app.simulator.analytics import generate_inventory_behavior
        result, bars = _run_with_trades()
        report = generate_inventory_behavior(result, bars)
        total = report.pct_time_long + report.pct_time_short + report.pct_time_flat
        assert abs(total - 100.0) < 0.1

    def test_autocorrelation_bounded(self):
        from app.simulator.analytics import generate_inventory_behavior
        result, bars = _run_with_trades()
        report = generate_inventory_behavior(result, bars)
        assert -1.0 <= report.position_autocorr_1 <= 1.0

    def test_to_dict_structure(self):
        from app.simulator.analytics import generate_inventory_behavior
        result, bars = _run_with_trades()
        d = generate_inventory_behavior(result, bars).to_dict()
        assert d["report_type"] == "inventory_behavior"
        assert "position" in d
        assert "holding" in d
        assert "turnover" in d

    def test_format_readable(self):
        from app.simulator.analytics import generate_inventory_behavior
        result, bars = _run_with_trades()
        text = generate_inventory_behavior(result, bars).format()
        assert "INVENTORY BEHAVIOR" in text


# ====================================================================
# Regime Behavior
# ====================================================================


class TestRegimeBehavior:

    def test_generates_vol_and_trend_regimes(self):
        from app.simulator.analytics import generate_regime_behavior
        result, bars = _run_with_trades(300)
        report = generate_regime_behavior(result, bars)
        assert len(report.vol_regimes) == 3
        assert len(report.trend_regimes) == 3

    def test_vol_regimes_cover_all_bars(self):
        from app.simulator.analytics import generate_regime_behavior
        result, bars = _run_with_trades(300)
        report = generate_regime_behavior(result, bars)
        total_bars = sum(r.n_bars for r in report.vol_regimes)
        assert total_bars == len(bars)

    def test_best_worst_regime_set(self):
        from app.simulator.analytics import generate_regime_behavior
        result, bars = _run_with_trades(300)
        report = generate_regime_behavior(result, bars)
        assert report.best_regime != ""
        assert report.worst_regime != ""

    def test_to_dict_structure(self):
        from app.simulator.analytics import generate_regime_behavior
        result, bars = _run_with_trades(300)
        d = generate_regime_behavior(result, bars).to_dict()
        assert d["report_type"] == "regime_behavior"
        assert "by_volatility" in d
        assert "by_trend" in d

    def test_format_readable(self):
        from app.simulator.analytics import generate_regime_behavior
        result, bars = _run_with_trades(300)
        text = generate_regime_behavior(result, bars).format()
        assert "REGIME BEHAVIOR" in text


# ====================================================================
# Parameter Stability
# ====================================================================


class TestParameterStability:

    def test_with_walk_forward_data(self):
        from app.simulator.analytics import generate_parameter_stability
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        wf = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
            symbol="EURUSD",
        )
        report = generate_parameter_stability(wf)
        assert report.n_windows > 0
        assert len(report.param_cv) > 0

    def test_stability_score_bounded(self):
        from app.simulator.analytics import generate_parameter_stability
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        wf = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
        )
        report = generate_parameter_stability(wf)
        assert 0 <= report.overall_stability_score <= 1.0

    def test_to_dict_structure(self):
        from app.simulator.analytics import generate_parameter_stability
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        wf = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
        )
        d = generate_parameter_stability(wf).to_dict()
        assert d["report_type"] == "parameter_stability"
        assert "stability" in d
        assert "verdict" in d

    def test_without_calibration_data(self):
        from app.simulator.analytics import generate_parameter_stability
        report = generate_parameter_stability(None)
        assert report.n_windows == 0

    def test_format_readable(self):
        from app.simulator.analytics import generate_parameter_stability
        from app.simulator.calibration import walk_forward_calibrate
        bars = _bars(800, vol=0.003)
        wf = walk_forward_calibrate(
            bars=bars, train_size=300, test_size=50, step_size=100,
        )
        text = generate_parameter_stability(wf).format()
        assert "PARAMETER STABILITY" in text


# ====================================================================
# Full Report (composite)
# ====================================================================


class TestFullReport:

    def test_generates_all_6_reports(self):
        from app.simulator.analytics import generate_full_report
        result, bars = _run_with_trades(300)
        report = generate_full_report(result, bars)
        assert report.backtest_summary is not None
        assert report.pnl_attribution is not None
        assert report.fill_toxicity is not None
        assert report.inventory_behavior is not None
        assert report.regime_behavior is not None
        # parameter_stability is None without calibration data
        assert report.parameter_stability is not None  # Empty but not None

    def test_to_dict_json_serializable(self):
        from app.simulator.analytics import generate_full_report
        result, bars = _run_with_trades(300)
        report = generate_full_report(result, bars)
        s = json.dumps(report.to_dict(), default=str)
        assert len(s) > 500

    def test_format_all_sections(self):
        from app.simulator.analytics import generate_full_report
        result, bars = _run_with_trades(300)
        report = generate_full_report(result, bars)
        text = report.format()
        assert "BACKTEST SUMMARY" in text
        assert "PNL ATTRIBUTION" in text
        assert "FILL TOXICITY" in text
        assert "INVENTORY BEHAVIOR" in text
        assert "REGIME BEHAVIOR" in text

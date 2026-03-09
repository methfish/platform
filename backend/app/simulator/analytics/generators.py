"""
Report generators — produce analytics reports from simulation results.

Each generator takes a SimulatorResult (and optionally bars and calibration
data) and returns a populated report schema.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.simulator.analytics.schemas import (
    BacktestSummaryReport,
    FillToxicityBucket,
    FillToxicityReport,
    FullAnalyticsReport,
    InventoryBehaviorReport,
    ParameterStabilityReport,
    ParamWindow,
    PnLAttributionReport,
    PnLBucket,
    RegimeBehaviorReport,
    RegimeBucket,
)
from app.simulator.engine import SimulatorResult
from app.simulator.inventory import ClosedTrade
from app.simulator.types import (
    InventorySnapshot,
    SimBar,
    SimulatorConfig,
)


# ---------------------------------------------------------------------------
# 1. Backtest Summary
# ---------------------------------------------------------------------------


def generate_backtest_summary(
    result: SimulatorResult,
    bars: Optional[list[SimBar]] = None,
) -> BacktestSummaryReport:
    """Generate a comprehensive backtest summary report."""

    cfg = result.config
    trades = result.trades
    eq = result.equity_curve

    initial = float(cfg.initial_capital)
    final = float(result.final_equity)
    ret_pct = ((final - initial) / initial * 100) if initial > 0 else 0.0

    # Gross PnL (sum of gross_pnl) vs net (sum of net_pnl)
    gross = sum(float(t.gross_pnl) for t in trades)
    net = sum(float(t.net_pnl) for t in trades)
    commission = sum(float(t.entry_commission + t.exit_commission) for t in trades)

    # Drawdown
    max_dd_pct = max((s.drawdown_pct for s in eq), default=0.0)
    peak_eq = max((float(s.peak_equity) for s in eq), default=initial)
    max_dd_usd = peak_eq * max_dd_pct / 100 if max_dd_pct > 0 else 0.0

    # Trade stats
    winners = [t for t in trades if float(t.net_pnl) > 0]
    losers = [t for t in trades if float(t.net_pnl) <= 0]
    n_trades = len(trades)
    win_rate = len(winners) / n_trades * 100 if n_trades > 0 else 0.0
    avg_win = sum(float(t.net_pnl) for t in winners) / len(winners) if winners else 0.0
    avg_loss = sum(float(t.net_pnl) for t in losers) / len(losers) if losers else 0.0
    total_wins = sum(float(t.net_pnl) for t in winners)
    total_losses = abs(sum(float(t.net_pnl) for t in losers))
    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf") if total_wins > 0 else 0.0
    avg_pnl = net / n_trades if n_trades > 0 else 0.0
    max_win = max((float(t.net_pnl) for t in trades), default=0.0)
    max_loss = min((float(t.net_pnl) for t in trades), default=0.0)

    # Holding period (in bars — approximate from timestamps)
    holding_bars_list = []
    if bars and trades:
        bar_dur = _bar_duration_hours(bars)
        for t in trades:
            if t.entry_time and t.exit_time:
                dur_hours = (t.exit_time - t.entry_time).total_seconds() / 3600
                holding_bars_list.append(dur_hours / bar_dur if bar_dur > 0 else 0)
    avg_holding = sum(holding_bars_list) / len(holding_bars_list) if holding_bars_list else 0.0

    # P5: Compute annualization factor from bar frequency
    bar_dur_hrs = _bar_duration_hours(bars)
    bars_per_year = (365.25 * 24) / bar_dur_hrs if bar_dur_hrs > 0 else 252.0
    sharpe = _compute_sharpe(eq, annual_factor=bars_per_year)
    sortino = _compute_sortino(eq, annual_factor=bars_per_year)
    calmar = (ret_pct / max_dd_pct) if max_dd_pct > 0 else 0.0

    # Execution
    fill_rate = (result.total_fills / result.total_orders * 100) if result.total_orders > 0 else 0.0

    # Time range
    start_time = eq[0].timestamp.isoformat() if eq else ""
    end_time = eq[-1].timestamp.isoformat() if eq else ""

    return BacktestSummaryReport(
        symbol=cfg.symbol,
        interval=bars[0].interval if bars else "",
        start_time=start_time,
        end_time=end_time,
        total_bars=result.total_bars,
        initial_capital=initial,
        final_equity=final,
        total_return_pct=ret_pct,
        gross_pnl=gross,
        net_pnl=net,
        total_commission=commission,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_usd=max_dd_usd,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        total_trades=n_trades,
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        avg_trade_pnl=avg_pnl,
        max_win=max_win,
        max_loss=max_loss,
        avg_holding_bars=avg_holding,
        total_orders=result.total_orders,
        total_fills=result.total_fills,
        total_cancels=result.total_cancels,
        total_rejects=result.total_rejects,
        fill_rate=fill_rate,
        kill_switch_triggered=result.kill_switch_trigger is not None,
        kill_switch_rule=result.kill_switch_trigger.rule if result.kill_switch_trigger else "",
    )


# ---------------------------------------------------------------------------
# 2. PnL Attribution
# ---------------------------------------------------------------------------


def generate_pnl_attribution(result: SimulatorResult) -> PnLAttributionReport:
    """Decompose PnL into alpha, spread, slippage, commission components."""

    trades = result.trades
    if not trades:
        return PnLAttributionReport()

    total_alpha = sum(float(t.attribution.alpha) for t in trades)
    total_spread = sum(float(t.attribution.spread_cost) for t in trades)
    total_slip = sum(float(t.attribution.slippage_cost) for t in trades)
    total_comm = sum(float(t.attribution.commission_cost) for t in trades)
    total_gross = sum(float(t.gross_pnl) for t in trades)
    total_net = sum(float(t.net_pnl) for t in trades)

    cost_pct = (
        (total_spread + total_slip + total_comm) / abs(total_alpha) * 100
        if abs(total_alpha) > 1e-10 else 0.0
    )

    # By side
    long_trades = [t for t in trades if t.side == "BUY"]
    short_trades = [t for t in trades if t.side == "SELL"]
    long_bucket = _make_pnl_bucket("LONG", long_trades, total_net)
    short_bucket = _make_pnl_bucket("SHORT", short_trades, total_net)

    # Cumulative time series
    cum_alpha, cum_spread, cum_slip, cum_comm, cum_net, cum_ts = [], [], [], [], [], []
    a, sp, sl, co, n = 0.0, 0.0, 0.0, 0.0, 0.0
    for t in trades:
        a += float(t.attribution.alpha)
        sp += float(t.attribution.spread_cost)
        sl += float(t.attribution.slippage_cost)
        co += float(t.attribution.commission_cost)
        n += float(t.net_pnl)
        cum_alpha.append(a)
        cum_spread.append(sp)
        cum_slip.append(sl)
        cum_comm.append(co)
        cum_net.append(n)
        cum_ts.append(t.exit_time.isoformat() if t.exit_time else "")

    return PnLAttributionReport(
        total_alpha=total_alpha,
        total_spread_cost=total_spread,
        total_slippage_cost=total_slip,
        total_commission_cost=total_comm,
        total_gross_pnl=total_gross,
        total_net_pnl=total_net,
        cost_as_pct_of_alpha=cost_pct,
        long_bucket=long_bucket,
        short_bucket=short_bucket,
        cumulative_alpha=cum_alpha,
        cumulative_spread=cum_spread,
        cumulative_slippage=cum_slip,
        cumulative_commission=cum_comm,
        cumulative_net=cum_net,
        cumulative_timestamps=cum_ts,
    )


# ---------------------------------------------------------------------------
# 3. Fill Toxicity
# ---------------------------------------------------------------------------


def generate_fill_toxicity(
    result: SimulatorResult,
    bars: list[SimBar],
) -> FillToxicityReport:
    """
    Measure fill toxicity — how much the market moves against us after fills.

    Uses the equity curve snapshots to measure mid-price movement
    relative to trade entry/exit prices.
    """
    trades = result.trades
    eq = result.equity_curve
    if not trades or not eq or not bars:
        return FillToxicityReport()

    # Build a mid-price lookup from bars
    mid_by_ts: dict[str, float] = {}
    bar_mids: list[float] = []
    for b in bars:
        mid = float(b.high + b.low + b.close) / 3.0
        mid_by_ts[b.timestamp.isoformat()] = mid
        bar_mids.append(mid)

    # For each trade, compute adverse selection at entry
    # Adverse = how much mid moved against us in the bar after entry
    bar_ts_list = [b.timestamp for b in bars]
    adverse_moves: list[float] = []
    maker_adverse: list[float] = []
    taker_adverse: list[float] = []
    winner_adverse: list[float] = []
    loser_adverse: list[float] = []

    for trade in trades:
        entry_idx = _find_bar_idx(bar_ts_list, trade.entry_time)
        if entry_idx is None or entry_idx + 1 >= len(bars):
            continue

        entry_mid = bar_mids[entry_idx]
        next_mid = bar_mids[entry_idx + 1]
        if entry_mid <= 0:
            continue

        # Adverse = mid moved against entry side
        if trade.side == "BUY":
            adverse_bps = (entry_mid - next_mid) / entry_mid * 10000
        else:
            adverse_bps = (next_mid - entry_mid) / entry_mid * 10000

        adverse_moves.append(adverse_bps)

        # We approximate: limit fills → maker, market fills → taker
        # Since we don't store fill type on ClosedTrade, use price proximity:
        # if entry_price ≈ entry_mid → likely taker (market order)
        # if entry_price differs → likely maker (limit order)
        spread_bps = float(result.config.spread_bps) / 2
        entry_diff_bps = abs(float(trade.entry_price) - entry_mid) / entry_mid * 10000
        if entry_diff_bps < spread_bps * 1.5:
            taker_adverse.append(adverse_bps)
        else:
            maker_adverse.append(adverse_bps)

        if float(trade.net_pnl) > 0:
            winner_adverse.append(adverse_bps)
        else:
            loser_adverse.append(adverse_bps)

    n = len(adverse_moves)
    if n == 0:
        return FillToxicityReport()

    mean_adverse = sum(adverse_moves) / n
    pct_adverse = sum(1 for a in adverse_moves if a > 0) / n * 100

    # Toxicity score: 0–1 based on how much adverse selection vs vol
    bar_vol = _std(bar_mids[:min(50, len(bar_mids))])
    if bar_vol > 0 and bar_mids:
        vol_bps = bar_vol / bar_mids[0] * 10000
        toxicity = min(1.0, max(0.0, abs(mean_adverse) / vol_bps))
    else:
        toxicity = 0.0

    # Rolling toxicity (window of 5 trades)
    rolling_tox = []
    rolling_ts = []
    window = min(5, n)
    for i in range(window - 1, n):
        chunk = adverse_moves[i - window + 1 : i + 1]
        rolling_tox.append(sum(chunk) / len(chunk))
        if i < len(trades) and trades[i].exit_time:
            rolling_ts.append(trades[i].exit_time.isoformat())
        else:
            rolling_ts.append("")

    return FillToxicityReport(
        overall_mean_adverse_bps=mean_adverse,
        overall_pct_adverse=pct_adverse,
        overall_toxicity_score=toxicity,
        maker_bucket=_make_toxicity_bucket("MAKER", maker_adverse),
        taker_bucket=_make_toxicity_bucket("TAKER", taker_adverse),
        winning_fills_adverse_bps=sum(winner_adverse) / len(winner_adverse) if winner_adverse else 0.0,
        losing_fills_adverse_bps=sum(loser_adverse) / len(loser_adverse) if loser_adverse else 0.0,
        rolling_toxicity=rolling_tox,
        rolling_timestamps=rolling_ts,
    )


# ---------------------------------------------------------------------------
# 4. Inventory Behavior
# ---------------------------------------------------------------------------


def generate_inventory_behavior(
    result: SimulatorResult,
    bars: Optional[list[SimBar]] = None,
) -> InventoryBehaviorReport:
    """Analyze how the strategy manages its inventory over time."""

    eq = result.equity_curve
    trades = result.trades
    if not eq:
        return InventoryBehaviorReport()

    positions = [float(s.net_qty) for s in eq]
    n = len(positions)

    mean_pos = sum(positions) / n if n > 0 else 0.0
    max_long = max(positions) if positions else 0.0
    max_short = min(positions) if positions else 0.0

    n_long = sum(1 for p in positions if p > 0)
    n_short = sum(1 for p in positions if p < 0)
    n_flat = sum(1 for p in positions if p == 0)
    pct_long = n_long / n * 100 if n > 0 else 0.0
    pct_short = n_short / n * 100 if n > 0 else 0.0
    pct_flat = n_flat / n * 100 if n > 0 else 0.0

    # Holding periods
    bar_dur = _bar_duration_hours(bars) if bars else 1.0
    holding_list = []
    for t in trades:
        if t.entry_time and t.exit_time:
            hrs = (t.exit_time - t.entry_time).total_seconds() / 3600
            holding_list.append(hrs / bar_dur if bar_dur > 0 else 0)

    mean_hold = sum(holding_list) / len(holding_list) if holding_list else 0.0
    sorted_hold = sorted(holding_list)
    median_hold = sorted_hold[len(sorted_hold) // 2] if sorted_hold else 0.0
    max_hold = max(holding_list) if holding_list else 0.0

    # Volume traded
    total_vol = sum(float(t.quantity) for t in trades) * 2  # entry + exit
    avg_abs_pos = sum(abs(p) for p in positions) / n if n > 0 else 0.0
    # Daily turnover (assume 24 bars/day for 1h data)
    bars_per_day = 24.0 / bar_dur if bar_dur > 0 else 24.0
    n_days = n / bars_per_day if bars_per_day > 0 else 1.0
    daily_turnover = (total_vol / n_days / avg_abs_pos) if avg_abs_pos > 0 and n_days > 0 else 0.0

    # Position autocorrelation (lag-1)
    autocorr = _autocorrelation(positions, lag=1)

    # Notional series
    notionals = []
    for s in eq:
        notional = abs(float(s.net_qty) * float(s.avg_entry_price))
        notionals.append(notional)
    mean_notional = sum(notionals) / len(notionals) if notionals else 0.0
    max_notional = max(notionals) if notionals else 0.0

    # Subsample time series for output (every 10th point)
    step = max(1, n // 100)
    ts_positions = positions[::step]
    ts_notionals = notionals[::step]
    ts_timestamps = [eq[i].timestamp.isoformat() for i in range(0, n, step)]

    return InventoryBehaviorReport(
        mean_position=mean_pos,
        max_long_position=max_long,
        max_short_position=max_short,
        pct_time_long=pct_long,
        pct_time_short=pct_short,
        pct_time_flat=pct_flat,
        mean_holding_bars=mean_hold,
        median_holding_bars=median_hold,
        max_holding_bars=max_hold,
        total_volume_traded=total_vol,
        daily_turnover=daily_turnover,
        position_autocorr_1=autocorr,
        mean_notional=mean_notional,
        max_notional=max_notional,
        position_series=ts_positions,
        notional_series=ts_notionals,
        timestamps=ts_timestamps,
    )


# ---------------------------------------------------------------------------
# 5. Regime Behavior
# ---------------------------------------------------------------------------


def generate_regime_behavior(
    result: SimulatorResult,
    bars: list[SimBar],
    vol_window: int = 20,
    trend_window: int = 20,
) -> RegimeBehaviorReport:
    """
    Analyze strategy performance across volatility and trend regimes.

    Volatility regimes: terciles of rolling realized vol.
    Trend regimes: sign of rolling return over trend_window bars.
    """
    if not bars or not result.equity_curve:
        return RegimeBehaviorReport()

    n = len(bars)
    if n < max(vol_window, trend_window) + 1:
        return RegimeBehaviorReport()

    # Compute rolling vol (close-to-close)
    closes = [float(b.close) for b in bars]
    log_rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]

    rolling_vol = [0.0]  # Pad first bar
    for i in range(len(log_rets)):
        if i < vol_window - 1:
            rolling_vol.append(0.0)
        else:
            chunk = log_rets[i - vol_window + 1 : i + 1]
            mean = sum(chunk) / len(chunk)
            var = sum((x - mean) ** 2 for x in chunk) / (len(chunk) - 1) if len(chunk) > 1 else 0
            rolling_vol.append(math.sqrt(var))

    # Vol terciles
    valid_vols = [v for v in rolling_vol if v > 0]
    if valid_vols:
        sorted_vols = sorted(valid_vols)
        t1 = sorted_vols[len(sorted_vols) // 3]
        t2 = sorted_vols[2 * len(sorted_vols) // 3]
    else:
        t1 = t2 = 0.0

    # Compute rolling trend
    rolling_trend = [0.0] * n
    for i in range(trend_window, n):
        if closes[i - trend_window] > 0:
            rolling_trend[i] = (closes[i] - closes[i - trend_window]) / closes[i - trend_window]

    # Assign regime labels per bar
    vol_labels = []
    trend_labels = []
    for i in range(n):
        v = rolling_vol[i] if i < len(rolling_vol) else 0
        if v <= t1:
            vol_labels.append("LOW_VOL")
        elif v <= t2:
            vol_labels.append("MED_VOL")
        else:
            vol_labels.append("HIGH_VOL")

        tr = rolling_trend[i]
        if tr > 0.001:
            trend_labels.append("UPTREND")
        elif tr < -0.001:
            trend_labels.append("DOWNTREND")
        else:
            trend_labels.append("FLAT")

    # Map trades to regimes
    bar_ts_list = [b.timestamp for b in bars]
    trades = result.trades

    # Build equity-curve returns for Sharpe per regime
    eq_returns = _equity_returns(result.equity_curve)

    # P5: Compute bars per year for proper annualization
    bar_dur = _bar_duration_hours(bars)
    bpy = (365.25 * 24) / bar_dur if bar_dur > 0 else 252.0

    # Aggregate by vol regime
    vol_regimes = _aggregate_regime(
        ["LOW_VOL", "MED_VOL", "HIGH_VOL"],
        vol_labels, rolling_vol, trades, bar_ts_list, eq_returns,
        bars_per_year=bpy,
    )
    # Aggregate by trend regime
    trend_regimes = _aggregate_regime(
        ["UPTREND", "FLAT", "DOWNTREND"],
        trend_labels, rolling_vol, trades, bar_ts_list, eq_returns,
        bars_per_year=bpy,
    )

    # Best/worst regime
    all_regimes = vol_regimes + trend_regimes
    if all_regimes:
        best = max(all_regimes, key=lambda r: r.sharpe)
        worst = min(all_regimes, key=lambda r: r.sharpe)
        sharpe_range = best.sharpe - worst.sharpe
    else:
        best = worst = RegimeBucket(label="N/A")
        sharpe_range = 0.0

    return RegimeBehaviorReport(
        vol_regimes=vol_regimes,
        trend_regimes=trend_regimes,
        best_regime=best.label,
        worst_regime=worst.label,
        regime_sharpe_range=sharpe_range,
    )


# ---------------------------------------------------------------------------
# 6. Parameter Stability
# ---------------------------------------------------------------------------


def generate_parameter_stability(
    walk_forward_result: Optional[object] = None,
) -> ParameterStabilityReport:
    """
    Analyze how calibrated parameters vary across walk-forward windows.

    Takes a WalkForwardResult from the calibration package.
    If not available, returns an empty report.
    """
    # Import here to avoid circular dependency
    from app.simulator.calibration.walk_forward import WalkForwardResult

    if walk_forward_result is None or not isinstance(walk_forward_result, WalkForwardResult):
        return ParameterStabilityReport()

    wf = walk_forward_result
    if not wf.windows:
        return ParameterStabilityReport(n_windows=0)

    # Extract key params across windows
    param_names = ["spread_bps", "slippage_bps", "queue_behind_pct",
                    "fill_rate_pct", "realized_vol_annualized"]
    param_values: dict[str, list[float]] = {n: [] for n in param_names}

    windows = []
    for win in wf.windows:
        pw = ParamWindow(window_idx=win.window_idx)
        for p in win.snapshot.parameters:
            if p.name in param_values:
                param_values[p.name].append(p.value)
            if p.name == "spread_bps":
                pw.spread_bps = p.value
            elif p.name == "slippage_bps":
                pw.slippage_bps = p.value
            elif p.name == "queue_behind_pct":
                pw.queue_behind_pct = p.value
            elif p.name == "fill_rate_pct":
                pw.fill_rate_pct = p.value
            elif p.name == "realized_vol_annualized":
                pw.realized_vol = p.value
        windows.append(pw)

    # Compute CV per parameter
    param_cv = {}
    param_means = {}
    param_stds = {}
    for name, values in param_values.items():
        if not values:
            continue
        mean = sum(values) / len(values)
        std = _std(values)
        cv = std / abs(mean) if abs(mean) > 1e-10 else 0.0
        param_cv[name] = cv
        param_means[name] = mean
        param_stds[name] = std

    # Overall stability score: 1 − mean(CV), clamped
    if param_cv:
        avg_cv = sum(param_cv.values()) / len(param_cv)
        overall = max(0.0, min(1.0, 1.0 - avg_cv))
    else:
        overall = 0.0

    most_stable = min(param_cv, key=param_cv.get) if param_cv else ""
    least_stable = max(param_cv, key=param_cv.get) if param_cv else ""

    return ParameterStabilityReport(
        n_windows=len(wf.windows),
        param_cv=param_cv,
        param_means=param_means,
        param_stds=param_stds,
        param_pnl_correlation={},  # Would need actual backtests per window
        windows=windows,
        most_stable_param=most_stable,
        least_stable_param=least_stable,
        overall_stability_score=overall,
    )


# ---------------------------------------------------------------------------
# Composite generator
# ---------------------------------------------------------------------------


def generate_full_report(
    result: SimulatorResult,
    bars: list[SimBar],
    walk_forward_result: Optional[object] = None,
) -> FullAnalyticsReport:
    """Generate all 6 reports from a simulation result."""

    return FullAnalyticsReport(
        backtest_summary=generate_backtest_summary(result, bars),
        pnl_attribution=generate_pnl_attribution(result),
        fill_toxicity=generate_fill_toxicity(result, bars),
        inventory_behavior=generate_inventory_behavior(result, bars),
        regime_behavior=generate_regime_behavior(result, bars),
        parameter_stability=generate_parameter_stability(walk_forward_result),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _bar_duration_hours(bars: Optional[list[SimBar]]) -> float:
    """Estimate bar duration in hours from first two bars."""
    if not bars or len(bars) < 2:
        return 1.0
    delta = (bars[1].timestamp - bars[0].timestamp).total_seconds() / 3600
    return max(delta, 0.0001)


def _compute_sharpe(eq: list[InventorySnapshot], annual_factor: float = 252.0) -> float:
    """Annualized Sharpe from equity curve snapshots."""
    if len(eq) < 2:
        return 0.0
    equities = [float(s.equity) for s in eq]
    returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]
    if not returns:
        return 0.0
    mean_r = sum(returns) / len(returns)
    std_r = _std(returns)
    if std_r == 0:
        return 0.0
    return (mean_r / std_r) * math.sqrt(annual_factor)


def _compute_sortino(eq: list[InventorySnapshot], annual_factor: float = 252.0) -> float:
    """Annualized Sortino from equity curve snapshots."""
    if len(eq) < 2:
        return 0.0
    equities = [float(s.equity) for s in eq]
    returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]
    if not returns:
        return 0.0
    mean_r = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf") if mean_r > 0 else 0.0
    # P6: Use len(returns) as denominator for downside deviation (not len(downside))
    down_var = sum(r ** 2 for r in downside) / len(returns)
    down_std = math.sqrt(down_var)
    if down_std == 0:
        return 0.0
    return (mean_r / down_std) * math.sqrt(annual_factor)


def _make_pnl_bucket(label: str, trades: list[ClosedTrade], total_net: float) -> PnLBucket:
    """Aggregate trades into a PnL bucket."""
    if not trades:
        return PnLBucket(label=label)
    gross = sum(float(t.gross_pnl) for t in trades)
    alpha = sum(float(t.attribution.alpha) for t in trades)
    spread = sum(float(t.attribution.spread_cost) for t in trades)
    slip = sum(float(t.attribution.slippage_cost) for t in trades)
    comm = sum(float(t.attribution.commission_cost) for t in trades)
    net = sum(float(t.net_pnl) for t in trades)
    pct = net / abs(total_net) * 100 if abs(total_net) > 1e-10 else 0.0
    return PnLBucket(
        label=label, n_trades=len(trades), gross_pnl=gross,
        alpha=alpha, spread_cost=spread, slippage_cost=slip,
        commission_cost=comm, net_pnl=net, pct_of_total=pct,
    )


def _make_toxicity_bucket(label: str, moves: list[float]) -> FillToxicityBucket:
    if not moves:
        return FillToxicityBucket(label=label)
    mean_adv = sum(moves) / len(moves)
    pct_adv = sum(1 for m in moves if m > 0) / len(moves) * 100
    return FillToxicityBucket(
        label=label, n_fills=len(moves),
        mean_adverse_bps=mean_adv, pct_adverse=pct_adv,
    )


def _find_bar_idx(bar_timestamps: list[datetime], target: Optional[datetime]) -> Optional[int]:
    """Find the bar index closest to a target timestamp."""
    if target is None or not bar_timestamps:
        return None
    # Linear scan (trades are few, bars are many but this is fine)
    best_idx = 0
    best_delta = abs((bar_timestamps[0] - target).total_seconds())
    for i in range(1, len(bar_timestamps)):
        delta = abs((bar_timestamps[i] - target).total_seconds())
        if delta < best_delta:
            best_delta = delta
            best_idx = i
        elif delta > best_delta:
            break  # Timestamps are sorted, so we can stop
    return best_idx


def _equity_returns(eq: list[InventorySnapshot]) -> list[float]:
    """Compute per-bar returns from equity curve."""
    if len(eq) < 2:
        return []
    equities = [float(s.equity) for s in eq]
    return [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]


def _aggregate_regime(
    labels: list[str],
    bar_labels: list[str],
    rolling_vol: list[float],
    trades: list[ClosedTrade],
    bar_timestamps: list[datetime],
    eq_returns: list[float],
    bars_per_year: float = 252.0,
) -> list[RegimeBucket]:
    """Aggregate trades and bars into regime buckets."""
    buckets = []
    for label in labels:
        # Count bars in this regime
        bar_indices = [i for i, bl in enumerate(bar_labels) if bl == label]
        n_bars = len(bar_indices)

        # Avg vol in this regime
        vols = [rolling_vol[i] for i in bar_indices if i < len(rolling_vol)]
        avg_vol = (sum(vols) / len(vols) * 100) if vols else 0.0  # As percentage

        # Trades in this regime (entry time falls in a bar of this regime)
        regime_trades = []
        for t in trades:
            idx = _find_bar_idx(bar_timestamps, t.entry_time)
            if idx is not None and idx < len(bar_labels) and bar_labels[idx] == label:
                regime_trades.append(t)

        n_trades = len(regime_trades)
        net_pnl = sum(float(t.net_pnl) for t in regime_trades)
        winners = sum(1 for t in regime_trades if float(t.net_pnl) > 0)
        win_rate = winners / n_trades * 100 if n_trades > 0 else 0.0

        # Sharpe from equity returns in this regime
        regime_returns = [
            eq_returns[i - 1] for i in bar_indices
            if 0 < i <= len(eq_returns)
        ]
        if regime_returns and len(regime_returns) > 1:
            mr = sum(regime_returns) / len(regime_returns)
            sr = _std(regime_returns)
            sharpe = (mr / sr * math.sqrt(bars_per_year)) if sr > 0 else 0.0
        else:
            sharpe = 0.0

        buckets.append(RegimeBucket(
            label=label, n_bars=n_bars, n_trades=n_trades,
            net_pnl=net_pnl, win_rate=win_rate,
            sharpe=sharpe, avg_vol=avg_vol,
        ))
    return buckets


def _std(values: list[float]) -> float:
    """Sample standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(var)


def _autocorrelation(values: list[float], lag: int = 1) -> float:
    """Lag-k autocorrelation (Pearson formula)."""
    n = len(values)
    if n < lag + 2:
        return 0.0
    mean = sum(values) / n
    # P7: Use proper variance (divided by n) as denominator
    variance = sum((v - mean) ** 2 for v in values) / n
    if variance == 0:
        return 0.0
    cov = sum(
        (values[i] - mean) * (values[i + lag] - mean)
        for i in range(n - lag)
    ) / (n - lag)
    return cov / variance

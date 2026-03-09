"""
Report schemas — structured dataclasses for all analytics reports.

Every report implements:
  - to_dict()  → JSON-serializable dict (machine-readable)
  - format()   → human-readable text (terminal / log output)

This separation lets the same report object serve both the API
(returns JSON) and the CLI (prints text).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _d(v: Decimal | float, dp: int = 4) -> float:
    """Decimal → rounded float for JSON."""
    return round(float(v), dp)


def _pct(v: float, dp: int = 2) -> str:
    return f"{v:.{dp}f}%"


def _usd(v: float, dp: int = 2) -> str:
    return f"${v:+,.{dp}f}"


# ---------------------------------------------------------------------------
# 1. Backtest Summary
# ---------------------------------------------------------------------------


@dataclass
class BacktestSummaryReport:
    """Top-level performance summary of a simulation run."""

    symbol: str = ""
    interval: str = ""
    start_time: str = ""
    end_time: str = ""
    total_bars: int = 0
    # Capital
    initial_capital: float = 0.0
    final_equity: float = 0.0
    total_return_pct: float = 0.0
    # PnL
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    total_commission: float = 0.0
    # Risk
    max_drawdown_pct: float = 0.0
    max_drawdown_usd: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    # Trades
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    avg_holding_bars: float = 0.0
    # Execution
    total_orders: int = 0
    total_fills: int = 0
    total_cancels: int = 0
    total_rejects: int = 0
    fill_rate: float = 0.0
    # Kill switch
    kill_switch_triggered: bool = False
    kill_switch_rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "backtest_summary",
            "symbol": self.symbol,
            "interval": self.interval,
            "period": {"start": self.start_time, "end": self.end_time},
            "bars": self.total_bars,
            "capital": {
                "initial": self.initial_capital,
                "final": self.final_equity,
                "return_pct": self.total_return_pct,
            },
            "pnl": {
                "gross": self.gross_pnl,
                "net": self.net_pnl,
                "commission": self.total_commission,
            },
            "risk": {
                "max_drawdown_pct": self.max_drawdown_pct,
                "max_drawdown_usd": self.max_drawdown_usd,
                "sharpe": self.sharpe_ratio,
                "sortino": self.sortino_ratio,
                "calmar": self.calmar_ratio,
            },
            "trades": {
                "total": self.total_trades,
                "winners": self.winning_trades,
                "losers": self.losing_trades,
                "win_rate": self.win_rate,
                "avg_win": self.avg_win,
                "avg_loss": self.avg_loss,
                "profit_factor": self.profit_factor,
                "avg_pnl": self.avg_trade_pnl,
                "max_win": self.max_win,
                "max_loss": self.max_loss,
                "avg_holding_bars": self.avg_holding_bars,
            },
            "execution": {
                "orders": self.total_orders,
                "fills": self.total_fills,
                "cancels": self.total_cancels,
                "rejects": self.total_rejects,
                "fill_rate": self.fill_rate,
            },
            "kill_switch": {
                "triggered": self.kill_switch_triggered,
                "rule": self.kill_switch_rule,
            },
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "BACKTEST SUMMARY",
            "=" * w,
            f"  Symbol:              {self.symbol}",
            f"  Interval:            {self.interval}",
            f"  Period:              {self.start_time} → {self.end_time}",
            f"  Bars:                {self.total_bars}",
            "",
            f"  Initial capital:     {_usd(self.initial_capital)}",
            f"  Final equity:        {_usd(self.final_equity)}",
            f"  Total return:        {_pct(self.total_return_pct)}",
            "",
            f"  Gross PnL:           {_usd(self.gross_pnl)}",
            f"  Net PnL:             {_usd(self.net_pnl)}",
            f"  Commission:          {_usd(self.total_commission)}",
            "",
            f"  Max drawdown:        {_pct(self.max_drawdown_pct)} ({_usd(self.max_drawdown_usd)})",
            f"  Sharpe ratio:        {self.sharpe_ratio:.2f}",
            f"  Sortino ratio:       {self.sortino_ratio:.2f}",
            f"  Calmar ratio:        {self.calmar_ratio:.2f}",
            "",
            f"  Trades:              {self.total_trades}",
            f"  Win rate:            {_pct(self.win_rate)}",
            f"  Avg win:             {_usd(self.avg_win)}",
            f"  Avg loss:            {_usd(self.avg_loss)}",
            f"  Profit factor:       {self.profit_factor:.2f}",
            f"  Max win:             {_usd(self.max_win)}",
            f"  Max loss:            {_usd(self.max_loss)}",
            f"  Avg holding:         {self.avg_holding_bars:.1f} bars",
            "",
            f"  Orders/fills/cancels/rejects: "
            f"{self.total_orders}/{self.total_fills}/{self.total_cancels}/{self.total_rejects}",
            f"  Fill rate:           {_pct(self.fill_rate)}",
        ]
        if self.kill_switch_triggered:
            lines.append(f"  KILL SWITCH:         {self.kill_switch_rule}")
        lines.append("=" * w)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. PnL Attribution
# ---------------------------------------------------------------------------


@dataclass
class PnLBucket:
    """PnL attribution for a group of trades."""

    label: str = ""
    n_trades: int = 0
    gross_pnl: float = 0.0
    alpha: float = 0.0
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0
    net_pnl: float = 0.0
    pct_of_total: float = 0.0


@dataclass
class PnLAttributionReport:
    """Decomposition of PnL into alpha, spread, slippage, commission."""

    # Overall
    total_alpha: float = 0.0
    total_spread_cost: float = 0.0
    total_slippage_cost: float = 0.0
    total_commission_cost: float = 0.0
    total_gross_pnl: float = 0.0
    total_net_pnl: float = 0.0
    cost_as_pct_of_alpha: float = 0.0
    # Per-side breakdown
    long_bucket: Optional[PnLBucket] = None
    short_bucket: Optional[PnLBucket] = None
    # Time-series: cumulative attribution over time
    cumulative_alpha: list[float] = field(default_factory=list)
    cumulative_spread: list[float] = field(default_factory=list)
    cumulative_slippage: list[float] = field(default_factory=list)
    cumulative_commission: list[float] = field(default_factory=list)
    cumulative_net: list[float] = field(default_factory=list)
    cumulative_timestamps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "pnl_attribution",
            "totals": {
                "alpha": self.total_alpha,
                "spread_cost": self.total_spread_cost,
                "slippage_cost": self.total_slippage_cost,
                "commission_cost": self.total_commission_cost,
                "gross_pnl": self.total_gross_pnl,
                "net_pnl": self.total_net_pnl,
                "cost_as_pct_of_alpha": self.cost_as_pct_of_alpha,
            },
            "by_side": {
                "long": _bucket_dict(self.long_bucket),
                "short": _bucket_dict(self.short_bucket),
            },
            "cumulative": {
                "timestamps": self.cumulative_timestamps,
                "alpha": self.cumulative_alpha,
                "spread": self.cumulative_spread,
                "slippage": self.cumulative_slippage,
                "commission": self.cumulative_commission,
                "net": self.cumulative_net,
            },
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "PNL ATTRIBUTION REPORT",
            "=" * w,
            f"  {'Component':<22} {'Amount':>12} {'% of Alpha':>12}",
            f"  {'─' * 20}  {'─' * 12} {'─' * 12}",
            f"  {'Alpha (edge)':22} {_usd(self.total_alpha):>12} {'100.0%':>12}",
        ]
        if self.total_alpha != 0:
            sp = self.total_spread_cost / abs(self.total_alpha) * 100
            sl = self.total_slippage_cost / abs(self.total_alpha) * 100
            co = self.total_commission_cost / abs(self.total_alpha) * 100
        else:
            sp = sl = co = 0.0
        lines += [
            f"  {'− Spread cost':22} {_usd(-self.total_spread_cost):>12} {_pct(sp):>12}",
            f"  {'− Slippage cost':22} {_usd(-self.total_slippage_cost):>12} {_pct(sl):>12}",
            f"  {'− Commission cost':22} {_usd(-self.total_commission_cost):>12} {_pct(co):>12}",
            f"  {'─' * 20}  {'─' * 12}",
            f"  {'= Net PnL':22} {_usd(self.total_net_pnl):>12}",
            f"  {'Cost / |Alpha|':22} {_pct(self.cost_as_pct_of_alpha):>12}",
        ]

        for label, bucket in [("LONG", self.long_bucket), ("SHORT", self.short_bucket)]:
            if bucket and bucket.n_trades > 0:
                lines += [
                    f"\n  {label} trades ({bucket.n_trades}):",
                    f"    Alpha:      {_usd(bucket.alpha):>12}   "
                    f"Spread: {_usd(-bucket.spread_cost):>12}   "
                    f"Net: {_usd(bucket.net_pnl):>12}",
                ]

        lines.append("=" * w)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Fill Toxicity
# ---------------------------------------------------------------------------


@dataclass
class FillToxicityBucket:
    """Toxicity metrics for a group of fills."""

    label: str = ""
    n_fills: int = 0
    mean_adverse_bps: float = 0.0
    median_adverse_bps: float = 0.0
    pct_adverse: float = 0.0        # % of fills that were adverse
    mean_favorable_bps: float = 0.0
    mean_vpin: float = 0.0          # Volume-clock probability of informed trading


@dataclass
class FillToxicityReport:
    """
    Measures how 'toxic' fills are — did the market move against us
    immediately after filling?

    High toxicity = adverse selection is eating our edge.
    """

    overall_mean_adverse_bps: float = 0.0
    overall_pct_adverse: float = 0.0
    overall_toxicity_score: float = 0.0   # 0-1, 1 = maximally toxic
    # By fill type
    maker_bucket: Optional[FillToxicityBucket] = None
    taker_bucket: Optional[FillToxicityBucket] = None
    # By trade outcome
    winning_fills_adverse_bps: float = 0.0
    losing_fills_adverse_bps: float = 0.0
    # Time series of rolling toxicity
    rolling_toxicity: list[float] = field(default_factory=list)
    rolling_timestamps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "fill_toxicity",
            "overall": {
                "mean_adverse_bps": self.overall_mean_adverse_bps,
                "pct_adverse": self.overall_pct_adverse,
                "toxicity_score": self.overall_toxicity_score,
            },
            "by_fill_type": {
                "maker": _toxicity_bucket_dict(self.maker_bucket),
                "taker": _toxicity_bucket_dict(self.taker_bucket),
            },
            "by_outcome": {
                "winning_fills_adverse_bps": self.winning_fills_adverse_bps,
                "losing_fills_adverse_bps": self.losing_fills_adverse_bps,
            },
            "rolling": {
                "timestamps": self.rolling_timestamps,
                "toxicity": self.rolling_toxicity,
            },
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "FILL TOXICITY REPORT",
            "=" * w,
            f"  Overall adverse selection:  {self.overall_mean_adverse_bps:+.2f} bps",
            f"  % fills adverse:           {_pct(self.overall_pct_adverse)}",
            f"  Toxicity score:            {self.overall_toxicity_score:.2f} / 1.00",
        ]
        for label, b in [("MAKER", self.maker_bucket), ("TAKER", self.taker_bucket)]:
            if b and b.n_fills > 0:
                lines += [
                    f"\n  {label} fills ({b.n_fills}):",
                    f"    Mean adverse:    {b.mean_adverse_bps:+.2f} bps",
                    f"    % adverse:       {_pct(b.pct_adverse)}",
                ]
        lines += [
            f"\n  Winning-trade fills:  {self.winning_fills_adverse_bps:+.2f} bps adverse",
            f"  Losing-trade fills:   {self.losing_fills_adverse_bps:+.2f} bps adverse",
            "=" * w,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Inventory Behavior
# ---------------------------------------------------------------------------


@dataclass
class InventoryBehaviorReport:
    """
    How the strategy manages inventory over time.

    Answers: how long are positions held? How large do they get?
    Is there mean-reversion or momentum in position changes?
    """

    # Position statistics
    mean_position: float = 0.0
    max_long_position: float = 0.0
    max_short_position: float = 0.0
    pct_time_long: float = 0.0
    pct_time_short: float = 0.0
    pct_time_flat: float = 0.0
    # Holding period
    mean_holding_bars: float = 0.0
    median_holding_bars: float = 0.0
    max_holding_bars: float = 0.0
    # Turnover
    total_volume_traded: float = 0.0
    daily_turnover: float = 0.0        # As fraction of avg position
    # Position autocorrelation
    position_autocorr_1: float = 0.0   # Lag-1 autocorrelation of position
    # Notional exposure
    mean_notional: float = 0.0
    max_notional: float = 0.0
    # Time series
    position_series: list[float] = field(default_factory=list)
    notional_series: list[float] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "inventory_behavior",
            "position": {
                "mean": self.mean_position,
                "max_long": self.max_long_position,
                "max_short": self.max_short_position,
                "pct_time_long": self.pct_time_long,
                "pct_time_short": self.pct_time_short,
                "pct_time_flat": self.pct_time_flat,
            },
            "holding": {
                "mean_bars": self.mean_holding_bars,
                "median_bars": self.median_holding_bars,
                "max_bars": self.max_holding_bars,
            },
            "turnover": {
                "total_volume": self.total_volume_traded,
                "daily_turnover": self.daily_turnover,
            },
            "autocorrelation": {"lag_1": self.position_autocorr_1},
            "notional": {
                "mean": self.mean_notional,
                "max": self.max_notional,
            },
            "series": {
                "timestamps": self.timestamps,
                "position": self.position_series,
                "notional": self.notional_series,
            },
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "INVENTORY BEHAVIOR REPORT",
            "=" * w,
            f"  Mean position:         {self.mean_position:+,.0f}",
            f"  Max long:              {self.max_long_position:+,.0f}",
            f"  Max short:             {self.max_short_position:+,.0f}",
            f"  % time long/short/flat:{_pct(self.pct_time_long)} / "
            f"{_pct(self.pct_time_short)} / {_pct(self.pct_time_flat)}",
            "",
            f"  Mean holding:          {self.mean_holding_bars:.1f} bars",
            f"  Median holding:        {self.median_holding_bars:.1f} bars",
            f"  Max holding:           {self.max_holding_bars:.0f} bars",
            "",
            f"  Total volume:          {self.total_volume_traded:,.0f}",
            f"  Daily turnover:        {self.daily_turnover:.2f}x",
            f"  Position autocorr(1):  {self.position_autocorr_1:.3f}",
            "",
            f"  Mean notional:         {_usd(self.mean_notional)}",
            f"  Max notional:          {_usd(self.max_notional)}",
            "=" * w,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Regime Behavior
# ---------------------------------------------------------------------------


@dataclass
class RegimeBucket:
    """Performance within a single market regime."""

    label: str = ""
    n_bars: int = 0
    n_trades: int = 0
    net_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    avg_vol: float = 0.0     # Avg realized vol in this regime


@dataclass
class RegimeBehaviorReport:
    """
    How the strategy performs across different market regimes.

    Regimes are defined by:
      - Volatility terciles (low / medium / high)
      - Trend direction (up / down / flat)
      - Combined (e.g., low-vol uptrend)
    """

    # By volatility
    vol_regimes: list[RegimeBucket] = field(default_factory=list)
    # By trend
    trend_regimes: list[RegimeBucket] = field(default_factory=list)
    # Best/worst regime
    best_regime: str = ""
    worst_regime: str = ""
    regime_sharpe_range: float = 0.0   # Spread between best and worst Sharpe

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "regime_behavior",
            "by_volatility": [_regime_dict(r) for r in self.vol_regimes],
            "by_trend": [_regime_dict(r) for r in self.trend_regimes],
            "best_regime": self.best_regime,
            "worst_regime": self.worst_regime,
            "regime_sharpe_range": self.regime_sharpe_range,
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "REGIME BEHAVIOR REPORT",
            "=" * w,
        ]
        lines.append(f"\n  BY VOLATILITY:")
        lines.append(
            f"  {'Regime':<14} {'Bars':>6} {'Trades':>7} "
            f"{'PnL':>10} {'WinRate':>8} {'Sharpe':>7} {'AvgVol':>8}"
        )
        lines.append(f"  {'─' * 12}  {'─' * 6} {'─' * 7} {'─' * 10} {'─' * 8} {'─' * 7} {'─' * 8}")
        for r in self.vol_regimes:
            lines.append(
                f"  {r.label:<14} {r.n_bars:>6} {r.n_trades:>7} "
                f"{_usd(r.net_pnl):>10} {_pct(r.win_rate):>8} "
                f"{r.sharpe:>7.2f} {_pct(r.avg_vol):>8}"
            )

        lines.append(f"\n  BY TREND:")
        lines.append(
            f"  {'Regime':<14} {'Bars':>6} {'Trades':>7} "
            f"{'PnL':>10} {'WinRate':>8} {'Sharpe':>7}"
        )
        lines.append(f"  {'─' * 12}  {'─' * 6} {'─' * 7} {'─' * 10} {'─' * 8} {'─' * 7}")
        for r in self.trend_regimes:
            lines.append(
                f"  {r.label:<14} {r.n_bars:>6} {r.n_trades:>7} "
                f"{_usd(r.net_pnl):>10} {_pct(r.win_rate):>8} "
                f"{r.sharpe:>7.2f}"
            )

        lines += [
            "",
            f"  Best regime:          {self.best_regime}",
            f"  Worst regime:         {self.worst_regime}",
            f"  Sharpe range:         {self.regime_sharpe_range:.2f}",
            "=" * w,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Parameter Stability
# ---------------------------------------------------------------------------


@dataclass
class ParamWindow:
    """One walk-forward window's parameter values."""

    window_idx: int = 0
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    queue_behind_pct: float = 0.0
    fill_rate_pct: float = 0.0
    realized_vol: float = 0.0
    net_pnl: float = 0.0         # Backtest PnL using that window's params
    sharpe: float = 0.0


@dataclass
class ParameterStabilityReport:
    """
    How stable are calibrated parameters across walk-forward windows,
    and how does strategy performance vary with parameter changes?
    """

    n_windows: int = 0
    # Per-parameter stability
    param_cv: dict[str, float] = field(default_factory=dict)
    param_means: dict[str, float] = field(default_factory=dict)
    param_stds: dict[str, float] = field(default_factory=dict)
    # Sensitivity: correlation between param changes and PnL changes
    param_pnl_correlation: dict[str, float] = field(default_factory=dict)
    # Per-window details
    windows: list[ParamWindow] = field(default_factory=list)
    # Verdict
    most_stable_param: str = ""
    least_stable_param: str = ""
    overall_stability_score: float = 0.0   # 0-1

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": "parameter_stability",
            "n_windows": self.n_windows,
            "stability": {
                "cv": self.param_cv,
                "means": self.param_means,
                "stds": self.param_stds,
            },
            "sensitivity": self.param_pnl_correlation,
            "windows": [
                {
                    "idx": pw.window_idx,
                    "spread_bps": pw.spread_bps,
                    "slippage_bps": pw.slippage_bps,
                    "queue_behind_pct": pw.queue_behind_pct,
                    "fill_rate_pct": pw.fill_rate_pct,
                    "realized_vol": pw.realized_vol,
                    "net_pnl": pw.net_pnl,
                    "sharpe": pw.sharpe,
                }
                for pw in self.windows
            ],
            "verdict": {
                "most_stable": self.most_stable_param,
                "least_stable": self.least_stable_param,
                "overall_score": self.overall_stability_score,
            },
        }

    def format(self) -> str:
        w = 70
        lines = [
            "=" * w,
            "PARAMETER STABILITY REPORT",
            "=" * w,
            f"  Windows analyzed: {self.n_windows}",
            f"  Overall stability score: {self.overall_stability_score:.2f} / 1.00",
            "",
            f"  {'Parameter':<22} {'Mean':>10} {'Std':>10} {'CV':>8} {'PnL corr':>10}",
            f"  {'─' * 20}  {'─' * 10} {'─' * 10} {'─' * 8} {'─' * 10}",
        ]
        for name in sorted(self.param_cv.keys()):
            cv = self.param_cv.get(name, 0)
            mean = self.param_means.get(name, 0)
            std = self.param_stds.get(name, 0)
            corr = self.param_pnl_correlation.get(name, 0)
            lines.append(
                f"  {name:<22} {mean:>10.4f} {std:>10.4f} "
                f"{cv:>8.3f} {corr:>+10.3f}"
            )

        if self.windows:
            lines += [
                "",
                f"  {'Win':>4} {'spread':>8} {'slip':>8} {'queue':>8} "
                f"{'fillrt':>8} {'vol':>8} {'PnL':>10} {'Sharpe':>7}",
                f"  {'─' * 3}  {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} "
                f"{'─' * 8} {'─' * 10} {'─' * 7}",
            ]
            for pw in self.windows:
                lines.append(
                    f"  {pw.window_idx:>4} {pw.spread_bps:>8.2f} "
                    f"{pw.slippage_bps:>8.2f} {pw.queue_behind_pct:>8.4f} "
                    f"{pw.fill_rate_pct:>8.4f} {pw.realized_vol:>8.4f} "
                    f"{_usd(pw.net_pnl):>10} {pw.sharpe:>7.2f}"
                )

        lines += [
            "",
            f"  Most stable:   {self.most_stable_param}",
            f"  Least stable:  {self.least_stable_param}",
            "=" * w,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Composite report
# ---------------------------------------------------------------------------


@dataclass
class FullAnalyticsReport:
    """All 6 reports bundled together."""

    backtest_summary: Optional[BacktestSummaryReport] = None
    pnl_attribution: Optional[PnLAttributionReport] = None
    fill_toxicity: Optional[FillToxicityReport] = None
    inventory_behavior: Optional[InventoryBehaviorReport] = None
    regime_behavior: Optional[RegimeBehaviorReport] = None
    parameter_stability: Optional[ParameterStabilityReport] = None
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"generated_at": self.generated_at}
        if self.backtest_summary:
            d["backtest_summary"] = self.backtest_summary.to_dict()
        if self.pnl_attribution:
            d["pnl_attribution"] = self.pnl_attribution.to_dict()
        if self.fill_toxicity:
            d["fill_toxicity"] = self.fill_toxicity.to_dict()
        if self.inventory_behavior:
            d["inventory_behavior"] = self.inventory_behavior.to_dict()
        if self.regime_behavior:
            d["regime_behavior"] = self.regime_behavior.to_dict()
        if self.parameter_stability:
            d["parameter_stability"] = self.parameter_stability.to_dict()
        return d

    def format(self) -> str:
        parts = []
        for report in [
            self.backtest_summary,
            self.pnl_attribution,
            self.fill_toxicity,
            self.inventory_behavior,
            self.regime_behavior,
            self.parameter_stability,
        ]:
            if report is not None:
                parts.append(report.format())
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def _bucket_dict(b: Optional[PnLBucket]) -> Optional[dict]:
    if b is None:
        return None
    return {
        "label": b.label, "n_trades": b.n_trades,
        "gross_pnl": b.gross_pnl, "alpha": b.alpha,
        "spread_cost": b.spread_cost, "slippage_cost": b.slippage_cost,
        "commission_cost": b.commission_cost, "net_pnl": b.net_pnl,
    }


def _toxicity_bucket_dict(b: Optional[FillToxicityBucket]) -> Optional[dict]:
    if b is None:
        return None
    return {
        "label": b.label, "n_fills": b.n_fills,
        "mean_adverse_bps": b.mean_adverse_bps,
        "pct_adverse": b.pct_adverse,
    }


def _regime_dict(r: RegimeBucket) -> dict:
    return {
        "label": r.label, "n_bars": r.n_bars, "n_trades": r.n_trades,
        "net_pnl": r.net_pnl, "win_rate": r.win_rate,
        "sharpe": r.sharpe, "avg_vol": r.avg_vol,
    }

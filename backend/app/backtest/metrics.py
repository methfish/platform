"""
Performance metrics calculator for backtesting and live strategies.

Computes standard quantitative finance metrics with emphasis on
the ones that matter for a small ($2k) account:
  - Sharpe ratio (risk-adjusted return)
  - Max drawdown (survival metric)
  - Win rate + expectancy (edge detection)
  - Fee drag (cost awareness)
  - Capital utilization (efficiency)

Avoids misleading metrics like raw return % without context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional


@dataclass
class Trade:
    """Single round-trip trade for metrics computation."""

    entry_time: datetime
    exit_time: datetime
    side: str               # BUY or SELL (entry side)
    symbol: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    commission: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")

    @property
    def gross_pnl(self) -> Decimal:
        if self.side == "BUY":
            return (self.exit_price - self.entry_price) * self.quantity
        return (self.entry_price - self.exit_price) * self.quantity

    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.commission - self.slippage_cost

    @property
    def return_pct(self) -> float:
        notional = self.entry_price * self.quantity
        if notional == 0:
            return 0.0
        return float(self.net_pnl / notional) * 100

    @property
    def holding_time(self) -> timedelta:
        return self.exit_time - self.entry_time

    @property
    def notional(self) -> Decimal:
        return self.entry_price * self.quantity

    @property
    def is_winner(self) -> bool:
        return self.net_pnl > 0


@dataclass
class EquityPoint:
    """Single point on the equity curve."""

    timestamp: datetime
    equity: Decimal
    drawdown: Decimal = Decimal("0")
    drawdown_pct: float = 0.0


@dataclass
class StrategyMetrics:
    """
    Complete metrics report for a strategy.

    All monetary values are in quote currency (usually USDT).
    """

    # Identity
    strategy_name: str = ""
    symbol: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    # Returns
    total_gross_pnl: Decimal = Decimal("0")
    total_net_pnl: Decimal = Decimal("0")
    total_return_pct: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Drawdown
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: Optional[timedelta] = None
    current_drawdown: Decimal = Decimal("0")

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # Expectancy
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    expectancy: Decimal = Decimal("0")  # $ expected per trade
    expectancy_ratio: float = 0.0       # Risk-adjusted expectancy

    # Holding
    avg_holding_time_minutes: float = 0.0
    median_holding_time_minutes: float = 0.0
    longest_trade_minutes: float = 0.0

    # Costs
    total_commission: Decimal = Decimal("0")
    total_slippage: Decimal = Decimal("0")
    fee_drag_pct: float = 0.0           # Fees as % of gross profit

    # Activity
    total_volume: Decimal = Decimal("0")
    avg_trade_size: Decimal = Decimal("0")
    trades_per_day: float = 0.0

    # Capital
    initial_capital: Decimal = Decimal("0")
    final_equity: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    capital_utilization_pct: float = 0.0  # Avg invested / capital

    # Equity curve
    equity_curve: list[EquityPoint] = field(default_factory=list)

    # Robustness flags
    is_trustworthy: bool = False
    trust_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for API responses."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "total_net_pnl": str(self.total_net_pnl),
            "total_gross_pnl": str(self.total_gross_pnl),
            "total_return_pct": round(self.total_return_pct, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "max_drawdown": str(self.max_drawdown),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "expectancy": str(self.expectancy),
            "expectancy_ratio": round(self.expectancy_ratio, 4),
            "avg_win": str(self.avg_win),
            "avg_loss": str(self.avg_loss),
            "avg_holding_time_minutes": round(self.avg_holding_time_minutes, 1),
            "total_commission": str(self.total_commission),
            "total_slippage": str(self.total_slippage),
            "fee_drag_pct": round(self.fee_drag_pct, 4),
            "total_volume": str(self.total_volume),
            "trades_per_day": round(self.trades_per_day, 2),
            "initial_capital": str(self.initial_capital),
            "final_equity": str(self.final_equity),
            "capital_utilization_pct": round(self.capital_utilization_pct, 2),
            "is_trustworthy": self.is_trustworthy,
            "trust_issues": self.trust_issues,
            "equity_curve": [
                {
                    "timestamp": ep.timestamp.isoformat(),
                    "equity": str(ep.equity),
                    "drawdown_pct": round(ep.drawdown_pct, 4),
                }
                for ep in self.equity_curve
            ],
        }


# ---------------------------------------------------------------------------
# Metrics Calculator
# ---------------------------------------------------------------------------

class MetricsCalculator:
    """
    Compute StrategyMetrics from a list of trades and initial capital.

    Usage:
        calc = MetricsCalculator(trades, initial_capital=Decimal("2000"))
        metrics = calc.compute()
    """

    def __init__(
        self,
        trades: list[Trade],
        initial_capital: Decimal = Decimal("2000"),
        risk_free_rate: float = 0.04,  # Annual risk-free rate
        strategy_name: str = "",
        symbol: str = "",
    ):
        self._trades = sorted(trades, key=lambda t: t.entry_time)
        self._initial_capital = initial_capital
        self._risk_free_rate = risk_free_rate
        self._strategy_name = strategy_name
        self._symbol = symbol

    def compute(self) -> StrategyMetrics:
        """Compute all metrics."""
        m = StrategyMetrics(
            strategy_name=self._strategy_name,
            symbol=self._symbol,
            initial_capital=self._initial_capital,
        )

        if not self._trades:
            m.trust_issues.append("NO_TRADES")
            return m

        m.period_start = self._trades[0].entry_time
        m.period_end = self._trades[-1].exit_time
        m.total_trades = len(self._trades)

        # --- P&L ---
        m.total_gross_pnl = sum(t.gross_pnl for t in self._trades)
        m.total_net_pnl = sum(t.net_pnl for t in self._trades)
        m.total_commission = sum(t.commission for t in self._trades)
        m.total_slippage = sum(t.slippage_cost for t in self._trades)
        m.total_volume = sum(t.notional for t in self._trades)

        if self._initial_capital > 0:
            m.total_return_pct = float(m.total_net_pnl / self._initial_capital) * 100

        # --- Win/Loss ---
        winners = [t for t in self._trades if t.is_winner]
        losers = [t for t in self._trades if not t.is_winner]
        m.winning_trades = len(winners)
        m.losing_trades = len(losers)

        if m.total_trades > 0:
            m.win_rate = m.winning_trades / m.total_trades

        gross_wins = sum(t.net_pnl for t in winners)
        gross_losses = abs(sum(t.net_pnl for t in losers))

        if m.winning_trades > 0:
            m.avg_win = gross_wins / m.winning_trades
        if m.losing_trades > 0:
            m.avg_loss = gross_losses / m.losing_trades

        # Profit factor
        if gross_losses > 0:
            m.profit_factor = float(gross_wins / gross_losses)
        elif gross_wins > 0:
            m.profit_factor = float("inf")

        # Expectancy
        if m.total_trades > 0:
            m.expectancy = m.total_net_pnl / m.total_trades
            if m.avg_loss > 0:
                m.expectancy_ratio = float(m.expectancy / m.avg_loss)

        # --- Equity Curve & Drawdown ---
        equity_curve, max_dd, max_dd_pct, max_dd_dur = self._compute_equity_curve()
        m.equity_curve = equity_curve
        m.max_drawdown = max_dd
        m.max_drawdown_pct = max_dd_pct
        m.max_drawdown_duration = max_dd_dur
        m.final_equity = self._initial_capital + m.total_net_pnl
        m.peak_equity = max(ep.equity for ep in equity_curve) if equity_curve else self._initial_capital

        if equity_curve:
            m.current_drawdown = m.peak_equity - m.final_equity

        # --- Risk-Adjusted Returns ---
        daily_returns = self._compute_daily_returns(equity_curve)
        m.sharpe_ratio = self._compute_sharpe(daily_returns)
        m.sortino_ratio = self._compute_sortino(daily_returns)
        if max_dd_pct != 0:
            m.calmar_ratio = m.total_return_pct / abs(max_dd_pct)

        # --- Holding Time ---
        holding_times = [t.holding_time.total_seconds() / 60 for t in self._trades]
        if holding_times:
            m.avg_holding_time_minutes = sum(holding_times) / len(holding_times)
            sorted_ht = sorted(holding_times)
            mid = len(sorted_ht) // 2
            m.median_holding_time_minutes = sorted_ht[mid]
            m.longest_trade_minutes = max(holding_times)

        # --- Activity ---
        if m.total_trades > 0:
            m.avg_trade_size = m.total_volume / m.total_trades
        if m.period_start and m.period_end:
            days = max((m.period_end - m.period_start).total_seconds() / 86400, 1)
            m.trades_per_day = m.total_trades / days

        # --- Fee Drag ---
        total_costs = m.total_commission + m.total_slippage
        if m.total_gross_pnl > 0:
            m.fee_drag_pct = float(total_costs / m.total_gross_pnl) * 100

        # --- Capital Utilization ---
        if self._initial_capital > 0 and m.total_trades > 0:
            avg_notional = m.total_volume / m.total_trades
            m.capital_utilization_pct = float(avg_notional / self._initial_capital) * 100

        # --- Trust Checks ---
        m.trust_issues = self._run_trust_checks(m)
        m.is_trustworthy = len(m.trust_issues) == 0

        return m

    def _compute_equity_curve(
        self,
    ) -> tuple[list[EquityPoint], Decimal, float, Optional[timedelta]]:
        """Build equity curve and compute drawdown stats."""
        curve: list[EquityPoint] = []
        equity = self._initial_capital
        peak = equity
        max_dd = Decimal("0")
        max_dd_pct = 0.0
        dd_start_time: Optional[datetime] = None
        max_dd_duration: Optional[timedelta] = None
        current_dd_start: Optional[datetime] = None

        curve.append(EquityPoint(
            timestamp=self._trades[0].entry_time if self._trades else datetime.now(),
            equity=equity,
        ))

        for trade in self._trades:
            equity += trade.net_pnl
            if equity > peak:
                peak = equity
                if current_dd_start is not None:
                    dur = trade.exit_time - current_dd_start
                    if max_dd_duration is None or dur > max_dd_duration:
                        max_dd_duration = dur
                    current_dd_start = None

            dd = peak - equity
            dd_pct = float(dd / peak) * 100 if peak > 0 else 0.0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

            if dd > 0 and current_dd_start is None:
                current_dd_start = trade.exit_time

            curve.append(EquityPoint(
                timestamp=trade.exit_time,
                equity=equity,
                drawdown=dd,
                drawdown_pct=dd_pct,
            ))

        # If still in drawdown at the end
        if current_dd_start is not None and self._trades:
            dur = self._trades[-1].exit_time - current_dd_start
            if max_dd_duration is None or dur > max_dd_duration:
                max_dd_duration = dur

        return curve, max_dd, max_dd_pct, max_dd_duration

    def _compute_daily_returns(self, curve: list[EquityPoint]) -> list[float]:
        """Aggregate equity curve into daily returns."""
        if len(curve) < 2:
            return []

        daily: dict[str, Decimal] = {}
        for ep in curve:
            day_key = ep.timestamp.strftime("%Y-%m-%d")
            daily[day_key] = ep.equity

        sorted_days = sorted(daily.items())
        returns = []
        for i in range(1, len(sorted_days)):
            prev_eq = sorted_days[i - 1][1]
            curr_eq = sorted_days[i][1]
            if prev_eq > 0:
                ret = float((curr_eq - prev_eq) / prev_eq)
                returns.append(ret)
        return returns

    def _compute_sharpe(self, daily_returns: list[float]) -> float:
        """Annualized Sharpe ratio."""
        if len(daily_returns) < 2:
            return 0.0
        mean_ret = sum(daily_returns) / len(daily_returns)
        std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1))
        if std_ret == 0:
            return 0.0
        daily_rf = self._risk_free_rate / 365
        sharpe = (mean_ret - daily_rf) / std_ret * math.sqrt(365)
        return sharpe

    def _compute_sortino(self, daily_returns: list[float]) -> float:
        """Annualized Sortino ratio (only penalizes downside vol)."""
        if len(daily_returns) < 2:
            return 0.0
        mean_ret = sum(daily_returns) / len(daily_returns)
        downside = [r for r in daily_returns if r < 0]
        if not downside:
            return float("inf") if mean_ret > 0 else 0.0
        downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
        if downside_std == 0:
            return 0.0
        daily_rf = self._risk_free_rate / 365
        sortino = (mean_ret - daily_rf) / downside_std * math.sqrt(365)
        return sortino

    def _run_trust_checks(self, m: StrategyMetrics) -> list[str]:
        """
        Flag issues that make backtest results untrustworthy.

        These checks enforce discipline and prevent premature deployment.
        """
        issues = []

        if m.total_trades < 30:
            issues.append(f"INSUFFICIENT_TRADES: {m.total_trades} trades (need 30+)")

        if m.period_start and m.period_end:
            days = (m.period_end - m.period_start).days
            if days < 30:
                issues.append(f"SHORT_PERIOD: {days} days (need 30+)")

        if m.max_drawdown_pct > 20:
            issues.append(f"HIGH_DRAWDOWN: {m.max_drawdown_pct:.1f}% (threshold 20%)")

        if m.fee_drag_pct > 50:
            issues.append(f"HIGH_FEE_DRAG: {m.fee_drag_pct:.1f}% of gross profit")

        if m.win_rate > 0.85:
            issues.append(f"SUSPICIOUSLY_HIGH_WIN_RATE: {m.win_rate:.1%}")

        if m.profit_factor > 5:
            issues.append(f"SUSPICIOUSLY_HIGH_PF: {m.profit_factor:.2f}")

        if m.sharpe_ratio > 4:
            issues.append(f"SUSPICIOUSLY_HIGH_SHARPE: {m.sharpe_ratio:.2f}")

        if m.total_return_pct > 100 and m.total_trades < 100:
            issues.append("HIGH_RETURN_FEW_TRADES: possible overfitting")

        return issues

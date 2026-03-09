"""
Backtesting engine for running strategies against historical OHLCV data.

Supports:
  - Grid trading
  - Market making
  - Mean reversion
  - Breakout filters
  - Cross-exchange arbitrage (simulated)

Design principles:
  - Realistic cost modeling (fees, slippage, spread)
  - Event-driven bar-by-bar processing
  - FIFO position tracking
  - Configurable fill assumptions
  - No lookahead bias
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from app.backtest.costs import CostModel, FOREX_RETAIL
from app.backtest.metrics import MetricsCalculator, StrategyMetrics, Trade

logger = logging.getLogger("pensy.backtest.engine")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class SignalSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Bar:
    """Single OHLCV bar for backtest processing."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    symbol: str = ""
    interval: str = ""


@dataclass
class BacktestOrder:
    """Internal order representation during backtest."""

    id: str = field(default_factory=lambda: str(uuid4())[:8])
    side: str = "BUY"
    price: Decimal = Decimal("0")       # Limit price (0 = market)
    quantity: Decimal = Decimal("0")
    order_type: str = "MARKET"          # MARKET or LIMIT
    filled: bool = False
    fill_price: Decimal = Decimal("0")
    fill_time: Optional[datetime] = None
    commission: Decimal = Decimal("0")
    slippage_cost: Decimal = Decimal("0")


@dataclass
class OpenPosition:
    """Active position being tracked during backtest."""

    side: str = "BUY"
    entry_price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    entry_time: Optional[datetime] = None
    unrealized_pnl: Decimal = Decimal("0")


@dataclass
class BacktestConfig:
    """Configuration for a single backtest run."""

    strategy_type: str = "grid"
    symbol: str = "EURUSD"
    interval: str = "1m"
    initial_capital: Decimal = Decimal("10000")
    cost_model: CostModel = field(default_factory=lambda: FOREX_RETAIL)
    strategy_params: dict[str, Any] = field(default_factory=dict)
    max_position_size: Decimal = Decimal("10000")
    stop_loss_pct: Optional[float] = 5.0           # % stop loss
    take_profit_pct: Optional[float] = None        # % take profit
    max_trades: int = 10000                         # Safety limit
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class BacktestResult:
    """Complete backtest result with trades and metrics."""

    id: str = field(default_factory=lambda: str(uuid4()))
    config: Optional[BacktestConfig] = None
    metrics: Optional[StrategyMetrics] = None
    trades: list[Trade] = field(default_factory=list)
    total_bars: int = 0
    status: str = "completed"
    error: Optional[str] = None
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "error": self.error,
            "total_bars": self.total_bars,
            "total_trades": len(self.trades),
            "run_at": self.run_at.isoformat(),
            "config": {
                "strategy_type": self.config.strategy_type if self.config else "",
                "symbol": self.config.symbol if self.config else "",
                "interval": self.config.interval if self.config else "",
                "initial_capital": str(self.config.initial_capital) if self.config else "0",
                "strategy_params": self.config.strategy_params if self.config else {},
            },
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


# ---------------------------------------------------------------------------
# Strategy Signals
# ---------------------------------------------------------------------------

class StrategySignalGenerator:
    """Generate trading signals from bar data based on strategy type."""

    @staticmethod
    def grid_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Grid trading: place buy/sell orders at grid levels.

        Params:
            grid_size_pct: distance between levels as %
            num_levels: number of grid levels
        """
        grid_pct = Decimal(str(params.get("grid_size_pct", 1.0)))
        center = state.get("center_price")
        if center is None:
            state["center_price"] = bar.close
            return SignalSide.HOLD, Decimal("0"), "initialized"

        center = Decimal(str(center))
        deviation_pct = ((bar.close - center) / center) * Decimal("100")

        if deviation_pct <= -grid_pct:
            state["center_price"] = float(bar.close)
            return SignalSide.BUY, bar.close, f"grid buy at -{deviation_pct:.2f}%"

        if deviation_pct >= grid_pct:
            state["center_price"] = float(bar.close)
            return SignalSide.SELL, bar.close, f"grid sell at +{deviation_pct:.2f}%"

        return SignalSide.HOLD, Decimal("0"), ""

    @staticmethod
    def mean_reversion_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Mean reversion: buy below SMA, sell above SMA.

        Params:
            sma_period: lookback period
            entry_std: standard deviations for entry
        """
        period = int(params.get("sma_period", 20))
        entry_std = float(params.get("entry_std", 2.0))

        prices = state.setdefault("price_history", [])
        prices.append(float(bar.close))

        if len(prices) < period:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        # Keep only needed history
        if len(prices) > period * 2:
            state["price_history"] = prices[-period * 2:]
            prices = state["price_history"]

        window = prices[-period:]
        sma = sum(window) / len(window)
        std = (sum((p - sma) ** 2 for p in window) / len(window)) ** 0.5

        if std == 0:
            return SignalSide.HOLD, Decimal("0"), "zero volatility"

        z_score = (float(bar.close) - sma) / std

        if z_score < -entry_std:
            return SignalSide.BUY, bar.close, f"z={z_score:.2f} below -{entry_std}"

        if z_score > entry_std:
            return SignalSide.SELL, bar.close, f"z={z_score:.2f} above +{entry_std}"

        return SignalSide.HOLD, Decimal("0"), f"z={z_score:.2f}"

    @staticmethod
    def market_making_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Simple MM: alternate buy/sell capturing the spread.

        Params:
            spread_bps: target spread in basis points
            inventory_limit: max inventory before skewing
        """
        spread_bps = Decimal(str(params.get("spread_bps", 10)))
        inv_limit = Decimal(str(params.get("inventory_limit", 5)))

        inventory = Decimal(str(state.get("inventory", 0)))
        last_side = state.get("last_side", "SELL")

        half_spread = bar.close * spread_bps / Decimal("20000")

        if last_side == "SELL" and inventory < inv_limit:
            state["last_side"] = "BUY"
            return SignalSide.BUY, bar.close - half_spread, "mm bid"

        if last_side == "BUY" and inventory > -inv_limit:
            state["last_side"] = "SELL"
            return SignalSide.SELL, bar.close + half_spread, "mm ask"

        return SignalSide.HOLD, Decimal("0"), f"inv={inventory}"

    @staticmethod
    def breakout_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Breakout: buy on new high, sell on new low over lookback period.

        Params:
            lookback: number of bars to track
        """
        lookback = int(params.get("lookback", 20))
        highs = state.setdefault("highs", [])
        lows = state.setdefault("lows", [])

        highs.append(float(bar.high))
        lows.append(float(bar.low))

        if len(highs) < lookback:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        if len(highs) > lookback * 2:
            state["highs"] = highs[-lookback * 2:]
            state["lows"] = lows[-lookback * 2:]
            highs = state["highs"]
            lows = state["lows"]

        recent_high = max(highs[-lookback:-1]) if len(highs) > 1 else float(bar.high)
        recent_low = min(lows[-lookback:-1]) if len(lows) > 1 else float(bar.low)

        if float(bar.close) > recent_high:
            return SignalSide.BUY, bar.close, f"breakout above {recent_high:.2f}"

        if float(bar.close) < recent_low:
            return SignalSide.SELL, bar.close, f"breakdown below {recent_low:.2f}"

        return SignalSide.HOLD, Decimal("0"), ""

    @staticmethod
    def sma_crossover_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Moving Average Crossover: buy when fast SMA crosses above slow SMA,
        sell when fast crosses below.

        Params:
            fast_period: fast SMA lookback (default 10)
            slow_period: slow SMA lookback (default 30)
        """
        fast_period = int(params.get("fast_period", 10))
        slow_period = int(params.get("slow_period", 30))

        prices = state.setdefault("price_history", [])
        prices.append(float(bar.close))

        if len(prices) < slow_period:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        # Trim excess history
        if len(prices) > slow_period * 3:
            state["price_history"] = prices[-slow_period * 3:]
            prices = state["price_history"]

        fast_sma = sum(prices[-fast_period:]) / fast_period
        slow_sma = sum(prices[-slow_period:]) / slow_period

        fast_above = fast_sma > slow_sma
        prev_fast_above = state.get("prev_fast_above")
        state["prev_fast_above"] = fast_above

        if prev_fast_above is None:
            return SignalSide.HOLD, Decimal("0"), "initialized crossover"

        # Crossover detection
        if fast_above and not prev_fast_above:
            return SignalSide.BUY, bar.close, f"fast SMA ({fast_sma:.4f}) crossed above slow ({slow_sma:.4f})"

        if not fast_above and prev_fast_above:
            return SignalSide.SELL, bar.close, f"fast SMA ({fast_sma:.4f}) crossed below slow ({slow_sma:.4f})"

        return SignalSide.HOLD, Decimal("0"), ""

    @staticmethod
    def rsi_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        RSI Mean Reversion: buy when RSI < oversold, sell when RSI > overbought.
        Uses Wilder smoothing for average gain/loss.

        Params:
            rsi_period: RSI lookback (default 14)
            oversold: buy threshold (default 30)
            overbought: sell threshold (default 70)
        """
        rsi_period = int(params.get("rsi_period", 14))
        oversold = float(params.get("oversold", 30))
        overbought = float(params.get("overbought", 70))

        prices = state.setdefault("price_history", [])
        prices.append(float(bar.close))

        if len(prices) < rsi_period + 1:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        # Compute price changes
        avg_gain = state.get("avg_gain")
        avg_loss = state.get("avg_loss")

        if avg_gain is None:
            # Initial SMA-based calculation
            gains = []
            losses = []
            for i in range(len(prices) - rsi_period, len(prices)):
                change = prices[i] - prices[i - 1]
                if change > 0:
                    gains.append(change)
                    losses.append(0.0)
                else:
                    gains.append(0.0)
                    losses.append(abs(change))
            avg_gain = sum(gains) / rsi_period
            avg_loss = sum(losses) / rsi_period
        else:
            # Wilder smoothing
            change = prices[-1] - prices[-2]
            current_gain = max(change, 0.0)
            current_loss = abs(min(change, 0.0))
            avg_gain = (avg_gain * (rsi_period - 1) + current_gain) / rsi_period
            avg_loss = (avg_loss * (rsi_period - 1) + current_loss) / rsi_period

        state["avg_gain"] = avg_gain
        state["avg_loss"] = avg_loss

        # Trim excess history
        if len(prices) > rsi_period * 3:
            state["price_history"] = prices[-rsi_period * 3:]

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        if rsi < oversold:
            return SignalSide.BUY, bar.close, f"RSI={rsi:.1f} < {oversold}"

        if rsi > overbought:
            return SignalSide.SELL, bar.close, f"RSI={rsi:.1f} > {overbought}"

        return SignalSide.HOLD, Decimal("0"), f"RSI={rsi:.1f}"

    @staticmethod
    def bollinger_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        Bollinger Bands: buy when price < lower band, sell when price > upper band.

        Params:
            bb_period: lookback period (default 20)
            num_std: number of standard deviations (default 2.0)
        """
        bb_period = int(params.get("bb_period", 20))
        num_std = float(params.get("num_std", 2.0))

        prices = state.setdefault("price_history", [])
        prices.append(float(bar.close))

        if len(prices) < bb_period:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        # Trim excess history
        if len(prices) > bb_period * 3:
            state["price_history"] = prices[-bb_period * 3:]
            prices = state["price_history"]

        window = prices[-bb_period:]
        sma = sum(window) / len(window)
        std = (sum((p - sma) ** 2 for p in window) / len(window)) ** 0.5

        if std == 0:
            return SignalSide.HOLD, Decimal("0"), "zero volatility"

        upper_band = sma + num_std * std
        lower_band = sma - num_std * std
        price = float(bar.close)

        if price < lower_band:
            return SignalSide.BUY, bar.close, f"price {price:.4f} < lower band {lower_band:.4f}"

        if price > upper_band:
            return SignalSide.SELL, bar.close, f"price {price:.4f} > upper band {upper_band:.4f}"

        return SignalSide.HOLD, Decimal("0"), ""

    @staticmethod
    def macd_signal(
        bar: Bar,
        params: dict,
        state: dict,
    ) -> tuple[SignalSide, Decimal, str]:
        """
        MACD Crossover: buy when MACD crosses above signal line,
        sell when MACD crosses below signal line.

        Params:
            fast_ema: fast EMA period (default 12)
            slow_ema: slow EMA period (default 26)
            signal_period: signal line EMA period (default 9)
        """
        fast_ema_period = int(params.get("fast_ema", 12))
        slow_ema_period = int(params.get("slow_ema", 26))
        signal_period = int(params.get("signal_period", 9))

        price = float(bar.close)

        # Initialize or update EMAs
        if "fast_ema" not in state:
            # Use first price as seed
            state["fast_ema"] = price
            state["slow_ema"] = price
            state["signal_ema"] = 0.0
            state["bar_count"] = 1
            state["prev_macd_above_signal"] = None
            return SignalSide.HOLD, Decimal("0"), "initializing"

        state["bar_count"] = state.get("bar_count", 0) + 1

        # EMA multipliers
        fast_mult = 2.0 / (fast_ema_period + 1)
        slow_mult = 2.0 / (slow_ema_period + 1)
        signal_mult = 2.0 / (signal_period + 1)

        # Update EMAs
        fast_ema_val = (price - state["fast_ema"]) * fast_mult + state["fast_ema"]
        slow_ema_val = (price - state["slow_ema"]) * slow_mult + state["slow_ema"]
        state["fast_ema"] = fast_ema_val
        state["slow_ema"] = slow_ema_val

        # MACD line
        macd_line = fast_ema_val - slow_ema_val

        # Need enough bars for slow EMA to be meaningful
        if state["bar_count"] < slow_ema_period:
            return SignalSide.HOLD, Decimal("0"), "warming up"

        # Signal line (EMA of MACD)
        if state["signal_ema"] == 0.0 and state["bar_count"] == slow_ema_period:
            state["signal_ema"] = macd_line
        else:
            state["signal_ema"] = (macd_line - state["signal_ema"]) * signal_mult + state["signal_ema"]

        signal_line = state["signal_ema"]

        macd_above_signal = macd_line > signal_line
        prev_macd_above = state.get("prev_macd_above_signal")
        state["prev_macd_above_signal"] = macd_above_signal

        if prev_macd_above is None:
            return SignalSide.HOLD, Decimal("0"), "initialized MACD"

        # Crossover detection
        if macd_above_signal and not prev_macd_above:
            return SignalSide.BUY, bar.close, f"MACD ({macd_line:.6f}) crossed above signal ({signal_line:.6f})"

        if not macd_above_signal and prev_macd_above:
            return SignalSide.SELL, bar.close, f"MACD ({macd_line:.6f}) crossed below signal ({signal_line:.6f})"

        return SignalSide.HOLD, Decimal("0"), ""


# ---------------------------------------------------------------------------
# Backtest Engine
# ---------------------------------------------------------------------------

SIGNAL_GENERATORS = {
    "grid": StrategySignalGenerator.grid_signal,
    "mean_reversion": StrategySignalGenerator.mean_reversion_signal,
    "market_making": StrategySignalGenerator.market_making_signal,
    "breakout": StrategySignalGenerator.breakout_signal,
    "sma_crossover": StrategySignalGenerator.sma_crossover_signal,
    "rsi": StrategySignalGenerator.rsi_signal,
    "bollinger": StrategySignalGenerator.bollinger_signal,
    "macd": StrategySignalGenerator.macd_signal,
}


class BacktestEngine:
    """
    Event-driven backtesting engine.

    Processes historical bars one by one, generates signals via a
    pluggable strategy, and tracks positions with realistic costs.

    Usage:
        engine = BacktestEngine(config)
        result = engine.run(bars)
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._signal_fn = SIGNAL_GENERATORS.get(config.strategy_type)
        if self._signal_fn is None:
            raise ValueError(f"Unknown strategy type: {config.strategy_type}. "
                             f"Available: {list(SIGNAL_GENERATORS.keys())}")
        self._equity = config.initial_capital
        self._position: Optional[OpenPosition] = None
        self._trades: list[Trade] = []
        self._state: dict = {}  # Strategy state
        self._bar_count = 0

    def run(self, bars: list[Bar]) -> BacktestResult:
        """
        Run the backtest over a list of bars.

        Returns a BacktestResult with trades and computed metrics.
        """
        try:
            for bar in bars:
                self._bar_count += 1
                self._process_bar(bar)

                if len(self._trades) >= self.config.max_trades:
                    logger.warning("Max trades reached: %d", self.config.max_trades)
                    break

            # Close any open position at the last bar price
            if self._position and bars:
                self._close_position(bars[-1], "end_of_backtest")

            # Compute metrics
            calc = MetricsCalculator(
                trades=self._trades,
                initial_capital=self.config.initial_capital,
                strategy_name=f"{self.config.strategy_type}_{self.config.symbol}",
                symbol=self.config.symbol,
            )
            metrics = calc.compute()

            return BacktestResult(
                config=self.config,
                metrics=metrics,
                trades=self._trades,
                total_bars=self._bar_count,
                status="completed",
            )

        except Exception as exc:
            logger.exception("Backtest error")
            return BacktestResult(
                config=self.config,
                total_bars=self._bar_count,
                trades=self._trades,
                status="error",
                error=str(exc),
            )

    def _process_bar(self, bar: Bar) -> None:
        """Process a single bar: check stops, generate signal, execute."""
        # Check stop loss / take profit on open position
        if self._position:
            self._check_exit_rules(bar)

        # Generate signal
        signal, price, reason = self._signal_fn(bar, self.config.strategy_params, self._state)

        if signal == SignalSide.HOLD:
            return

        if signal == SignalSide.BUY:
            if self._position is None:
                self._open_position(bar, "BUY", reason)
            elif self._position.side == "SELL":
                self._close_position(bar, f"reverse: {reason}")
                self._open_position(bar, "BUY", reason)

        elif signal == SignalSide.SELL:
            if self._position is None:
                self._open_position(bar, "SELL", reason)
            elif self._position.side == "BUY":
                self._close_position(bar, f"reverse: {reason}")
                self._open_position(bar, "SELL", reason)

    def _open_position(self, bar: Bar, side: str, reason: str) -> None:
        """Open a new position with cost modeling."""
        quantity = self.config.max_position_size
        cost_info = self.config.cost_model.compute_total_cost(
            bar.close, quantity, side
        )

        self._position = OpenPosition(
            side=side,
            entry_price=cost_info["execution_price"],
            quantity=quantity,
            entry_time=bar.timestamp,
        )

        # Update MM inventory state
        if self.config.strategy_type == "market_making":
            inv = Decimal(str(self._state.get("inventory", 0)))
            if side == "BUY":
                self._state["inventory"] = float(inv + quantity)
            else:
                self._state["inventory"] = float(inv - quantity)

    def _close_position(self, bar: Bar, reason: str) -> None:
        """Close current position and record the trade."""
        if self._position is None:
            return

        exit_side = "SELL" if self._position.side == "BUY" else "BUY"
        cost_info = self.config.cost_model.compute_total_cost(
            bar.close, self._position.quantity, exit_side
        )

        # Entry cost (commission was paid on entry too)
        entry_cost = self.config.cost_model.compute_commission(
            self._position.entry_price * self._position.quantity
        )

        trade = Trade(
            entry_time=self._position.entry_time or bar.timestamp,
            exit_time=bar.timestamp,
            side=self._position.side,
            symbol=self.config.symbol,
            entry_price=self._position.entry_price,
            exit_price=cost_info["execution_price"],
            quantity=self._position.quantity,
            commission=entry_cost + cost_info["commission"],
            slippage_cost=cost_info["slippage_cost"],
        )

        self._trades.append(trade)
        self._equity += trade.net_pnl
        self._position = None

    def _check_exit_rules(self, bar: Bar) -> None:
        """Check stop loss and take profit on open position."""
        if self._position is None:
            return

        if self._position.side == "BUY":
            pnl_pct = float((bar.close - self._position.entry_price) / self._position.entry_price) * 100
        else:
            pnl_pct = float((self._position.entry_price - bar.close) / self._position.entry_price) * 100

        # Stop loss
        if self.config.stop_loss_pct and pnl_pct <= -self.config.stop_loss_pct:
            self._close_position(bar, f"stop_loss at {pnl_pct:.2f}%")
            return

        # Take profit
        if self.config.take_profit_pct and pnl_pct >= self.config.take_profit_pct:
            self._close_position(bar, f"take_profit at {pnl_pct:.2f}%")


# ---------------------------------------------------------------------------
# Parameter Sweep
# ---------------------------------------------------------------------------

@dataclass
class SweepResult:
    """Result of a parameter sweep."""

    params: dict
    metrics: StrategyMetrics
    rank_score: float = 0.0


def run_parameter_sweep(
    bars: list[Bar],
    strategy_type: str,
    symbol: str,
    param_grid: dict[str, list],
    initial_capital: Decimal = Decimal("10000"),
    cost_model: CostModel = FOREX_RETAIL,
    max_position_size: Decimal = Decimal("10000"),
) -> list[SweepResult]:
    """
    Sweep over parameter combinations and rank results.

    Ranking uses: Sharpe * sqrt(trades) / (1 + max_dd_pct)
    This penalizes low trade counts and high drawdowns.
    """
    import itertools

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(itertools.product(*values))

    results: list[SweepResult] = []

    for combo in combos:
        params = dict(zip(keys, combo))

        config = BacktestConfig(
            strategy_type=strategy_type,
            symbol=symbol,
            initial_capital=initial_capital,
            cost_model=cost_model,
            strategy_params=params,
            max_position_size=max_position_size,
        )

        engine = BacktestEngine(config)
        result = engine.run(bars)

        if result.metrics and result.metrics.total_trades > 0:
            m = result.metrics
            # Robustness-weighted score
            trade_factor = min(m.total_trades ** 0.5, 10)  # Cap benefit
            dd_penalty = 1 + abs(m.max_drawdown_pct) / 100
            score = m.sharpe_ratio * trade_factor / dd_penalty

            results.append(SweepResult(
                params=params,
                metrics=m,
                rank_score=score,
            ))

    results.sort(key=lambda r: r.rank_score, reverse=True)
    return results

"""
Request/response schemas for the research & backtest API.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------

class DataCollectionRequest(BaseModel):
    exchange: str = Field("binance", description="CCXT exchange id")
    symbols: list[str] = Field(
        default=["BTC/USDT", "ETH/USDT"],
        description="Symbols to collect (CCXT format)",
    )
    intervals: list[str] = Field(
        default=["1m", "5m"],
        description="Candle intervals",
    )
    limit: int = Field(500, ge=1, le=1000, description="Candles per request")


class DataCollectionStatus(BaseModel):
    job_id: str
    exchange: str
    status: str
    symbols_total: int
    symbols_done: int
    bars_inserted: int
    bars_skipped: int
    errors: list[str]
    progress_pct: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DataSummaryResponse(BaseModel):
    datasets: list[dict]
    total_bars: int


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    strategy_type: str = Field(
        ...,
        description="Strategy type: grid, mean_reversion, market_making, breakout",
    )
    symbol: str = Field("BTCUSDT", description="Trading symbol")
    interval: str = Field("5m", description="Candle interval to backtest on")
    initial_capital: Decimal = Field(
        Decimal("2000"), ge=0, description="Starting capital in USDT"
    )
    cost_model: str = Field(
        "binance_spot",
        description="Cost model: binance_spot, conservative, zero",
    )
    strategy_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Strategy-specific parameters",
    )
    max_position_size: Decimal = Field(
        Decimal("0.01"), description="Max position in base asset"
    )
    stop_loss_pct: Optional[float] = Field(
        5.0, description="Stop loss % (null to disable)"
    )
    take_profit_pct: Optional[float] = Field(
        None, description="Take profit % (null to disable)"
    )
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class BacktestResponse(BaseModel):
    id: str
    status: str
    total_bars: int
    total_trades: int
    run_at: datetime
    config: dict
    metrics: Optional[dict] = None
    error: Optional[str] = None


class BacktestListItem(BaseModel):
    id: str
    strategy_type: str
    symbol: str
    interval: str
    status: str
    total_trades: int
    net_pnl: str
    sharpe_ratio: str
    max_drawdown_pct: str
    win_rate: str
    is_trustworthy: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Parameter Sweep
# ---------------------------------------------------------------------------

class ParameterSweepRequest(BaseModel):
    strategy_type: str
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    initial_capital: Decimal = Decimal("2000")
    param_grid: dict[str, list] = Field(
        ...,
        description="Dict of param_name -> list of values to sweep",
    )
    max_position_size: Decimal = Decimal("0.01")


class SweepResultItem(BaseModel):
    params: dict
    sharpe_ratio: float
    net_pnl: str
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    profit_factor: float
    rank_score: float
    is_trustworthy: bool


class ParameterSweepResponse(BaseModel):
    strategy_type: str
    symbol: str
    total_combinations: int
    results: list[SweepResultItem]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class EquityCurvePoint(BaseModel):
    timestamp: datetime
    equity: str
    drawdown_pct: float


class StrategyMetricsResponse(BaseModel):
    strategy_name: str
    symbol: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    total_net_pnl: str
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate: float
    profit_factor: float
    expectancy: str
    avg_holding_time_minutes: float
    total_commission: str
    fee_drag_pct: float
    trades_per_day: float
    is_trustworthy: bool
    trust_issues: list[str]
    equity_curve: list[EquityCurvePoint]


# ---------------------------------------------------------------------------
# Research Dashboard
# ---------------------------------------------------------------------------

class ResearchDashboardResponse(BaseModel):
    """Aggregated dashboard data for the quant research view."""

    # Data status
    data_summary: DataSummaryResponse

    # Strategy performance overview
    active_strategies: int = 0
    total_backtests: int = 0
    best_sharpe: Optional[dict] = None
    worst_drawdown: Optional[dict] = None

    # Recent activity
    recent_backtests: list[BacktestListItem] = []
    live_strategy_pnl: dict[str, str] = {}

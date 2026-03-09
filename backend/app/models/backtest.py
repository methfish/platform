"""
BacktestRun model — persists backtest configurations and results.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BacktestRun(Base):
    """Stores configuration and results of a single backtest execution."""

    __tablename__ = "backtest_runs"

    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="running")

    # Config
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=True)
    cost_model_name: Mapped[str] = mapped_column(String(32), default="binance_spot")

    # Results summary
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_bars: Mapped[int] = mapped_column(Integer, default=0)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    sharpe_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    win_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), default=Decimal("0"))
    profit_factor: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    expectancy: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    total_commission: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    fee_drag_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    trades_per_day: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0"))

    # Full metrics JSON for detailed retrieval
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Equity curve (list of {timestamp, equity, drawdown_pct})
    equity_curve_json: Mapped[list] = mapped_column(JSONB, nullable=True)

    # Trust
    is_trustworthy: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_issues: Mapped[list] = mapped_column(JSONB, nullable=True)

    error: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_backtest_strategy_type", "strategy_type"),
        Index("ix_backtest_symbol", "symbol"),
        Index("ix_backtest_created", "created_at"),
    )

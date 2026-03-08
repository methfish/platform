"""Market data cache metadata model (optional DB persistence for OHLCV)."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TickerSnapshot(Base):
    __tablename__ = "ticker_snapshots"

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    bid: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    ask: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    last: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    volume_24h: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_ticker_snap_symbol_time", "symbol", "snapshot_time"),
    )


class OHLCVBar(Base):
    """Single OHLCV candlestick bar persisted from exchange kline data."""

    __tablename__ = "ohlcv_bars"

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_volume: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    trades: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index(
            "ix_ohlcv_symbol_interval_time",
            "symbol",
            "interval",
            "open_time",
            unique=True,
        ),
    )

"""
Position and PositionSnapshot SQLAlchemy models.

Positions represent the current state per symbol/exchange/trading_mode.
Snapshots capture point-in-time state for historical analysis.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Position(Base):
    __tablename__ = "positions"

    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False, default="FLAT")
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    avg_entry_price: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    total_commission: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="PAPER")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "trading_mode", name="uq_position_key"),
        Index("ix_positions_symbol", "symbol"),
        Index("ix_positions_trading_mode", "trading_mode"),
    )

    def __repr__(self) -> str:
        return (
            f"<Position {self.exchange}:{self.symbol} {self.side} "
            f"qty={self.quantity} avg={self.avg_entry_price} mode={self.trading_mode}>"
        )


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    position_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("positions.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    mark_price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    total_equity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_position_snapshots_time", "snapshot_time"),
        Index("ix_position_snapshots_position_id", "position_id"),
    )

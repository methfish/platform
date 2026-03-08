"""
Order and OrderFill SQLAlchemy models.

Orders are the central entity. Every order is tagged with trading_mode
(PAPER/LIVE) and persists through its full lifecycle. Fills are immutable
records of partial or full executions.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID as PyUUID
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    # Identifiers
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exchange_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # References
    strategy_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), nullable=True
    )

    # Order details
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY/SELL
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # MARKET/LIMIT/etc
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    time_in_force: Mapped[str] = mapped_column(String(8), default="GTC")

    # State
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="PAPER")
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    fills: Mapped[list["OrderFill"]] = relationship(back_populates="order", lazy="selectin")

    __table_args__ = (
        Index("ix_orders_status", "status"),
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_trading_mode", "trading_mode"),
        Index("ix_orders_exchange", "exchange"),
        Index("ix_orders_strategy_id", "strategy_id"),
        Index("ix_orders_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Order {self.client_order_id} {self.symbol} "
            f"{self.side} {self.order_type} {self.quantity}@{self.price} "
            f"status={self.status} mode={self.trading_mode}>"
        )


class OrderFill(Base):
    __tablename__ = "order_fills"

    order_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False
    )
    exchange_fill_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(28, 12), default=Decimal("0"))
    commission_asset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fill_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="fills")

    __table_args__ = (
        Index("ix_order_fills_order_id", "order_id"),
        Index("ix_order_fills_fill_time", "fill_time"),
    )

    def __repr__(self) -> str:
        return f"<OrderFill {self.quantity}@{self.price} order={self.order_id}>"

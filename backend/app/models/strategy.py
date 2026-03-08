"""Strategy SQLAlchemy model."""

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Strategy(Base):
    __tablename__ = "strategies"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PAUSED")
    trading_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="PAPER")
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_strategies_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Strategy {self.name} type={self.strategy_type} status={self.status}>"

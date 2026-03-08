"""Risk event SQLAlchemy model."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RiskEvent(Base):
    __tablename__ = "risk_events"

    order_id: Mapped[uuid4 | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True
    )
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)  # PASS/FAIL/WARN
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_risk_events_order_id", "order_id"),
        Index("ix_risk_events_check_name", "check_name"),
        Index("ix_risk_events_evaluated_at", "evaluated_at"),
    )

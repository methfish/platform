"""Reconciliation run and break SQLAlchemy models."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    run_type: Mapped[str] = mapped_column(String(16), nullable=False)  # SCHEDULED/MANUAL
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RUNNING")
    breaks_found: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    breaks: Mapped[list["ReconciliationBreak"]] = relationship(
        back_populates="run", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_recon_runs_exchange", "exchange"),
        Index("ix_recon_runs_started_at", "started_at"),
    )


class ReconciliationBreak(Base):
    __tablename__ = "reconciliation_breaks"

    run_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id"), nullable=False
    )
    break_type: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    internal_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exchange_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["ReconciliationRun"] = relationship(back_populates="breaks")

    __table_args__ = (
        Index("ix_recon_breaks_run_id", "run_id"),
    )

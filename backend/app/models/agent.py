"""
Agent and Skill system SQLAlchemy models.

Tables:
    - skill_definitions: Registered skill metadata.
    - agent_runs: Each full pipeline execution for an agent.
    - skill_invocations: Every skill execution log (append-only audit trail).
    - learned_lessons: Lessons extracted by Agent B for future reference.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SkillDefinition(Base):
    """Metadata about a registered skill. Updated at startup."""

    __tablename__ = "skill_definitions"

    skill_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_type: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MEDIUM"
    )
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_skill_defs_skill_id", "skill_id"),
        Index("ix_skill_defs_execution_type", "execution_type"),
    )


class AgentRun(Base):
    """Record of a full agent pipeline execution."""

    __tablename__ = "agent_runs"

    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=True)
    short_circuited: Mapped[bool] = mapped_column(Boolean, default=False)
    short_circuit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    skills_run: Mapped[int] = mapped_column(Integer, default=0)
    skills_failed: Mapped[int] = mapped_column(Integer, default=0)
    skills_skipped: Mapped[int] = mapped_column(Integer, default=0)
    result_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trading_mode: Mapped[str] = mapped_column(String(8), default="PAPER")

    invocations: Mapped[list["SkillInvocation"]] = relationship(
        back_populates="agent_run", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_agent_runs_agent_type", "agent_type"),
        Index("ix_agent_runs_created_at", "created_at"),
        Index("ix_agent_runs_correlation_id", "correlation_id"),
    )


class SkillInvocation(Base):
    """Append-only audit log for every skill execution."""

    __tablename__ = "skill_invocations"

    agent_run_id: Mapped[uuid4 | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_type: Mapped[str] = mapped_column(String(24), nullable=False)
    input_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1.0.0"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_run: Mapped["AgentRun | None"] = relationship(
        back_populates="invocations"
    )

    __table_args__ = (
        Index("ix_skill_invocations_skill_id", "skill_id"),
        Index("ix_skill_invocations_agent_type", "agent_type"),
        Index("ix_skill_invocations_status", "status"),
        Index("ix_skill_invocations_created_at", "created_at"),
    )


class LearnedLesson(Base):
    """Lessons extracted by the Failure Analysis Agent."""

    __tablename__ = "learned_lessons"

    agent_run_id: Mapped[uuid4 | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="INFO"
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_order_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_lessons_category", "category"),
        Index("ix_lessons_severity", "severity"),
        Index("ix_lessons_created_at", "created_at"),
        Index("ix_lessons_applied", "applied"),
    )

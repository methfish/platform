"""Add agent skill system tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- skill_definitions ---
    op.create_table(
        "skill_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("skill_id", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("execution_type", sa.String(24), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column("requires_human_review", sa.Boolean, server_default="false"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("config_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_skill_defs_skill_id", "skill_definitions", ["skill_id"])
    op.create_index("ix_skill_defs_execution_type", "skill_definitions", ["execution_type"])

    # --- agent_runs ---
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_type", sa.String(32), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("completed", sa.Boolean, server_default="true"),
        sa.Column("short_circuited", sa.Boolean, server_default="false"),
        sa.Column("short_circuit_reason", sa.Text, nullable=True),
        sa.Column("total_execution_time_ms", sa.Float, server_default="0"),
        sa.Column("skills_run", sa.Integer, server_default="0"),
        sa.Column("skills_failed", sa.Integer, server_default="0"),
        sa.Column("skills_skipped", sa.Integer, server_default="0"),
        sa.Column("result_summary_json", postgresql.JSONB, nullable=True),
        sa.Column("trading_mode", sa.String(8), server_default="PAPER"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])
    op.create_index("ix_agent_runs_correlation_id", "agent_runs", ["correlation_id"])

    # --- skill_invocations ---
    op.create_table(
        "skill_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=True,
        ),
        sa.Column("skill_id", sa.String(64), nullable=False),
        sa.Column("agent_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("execution_type", sa.String(24), nullable=False),
        sa.Column("input_summary", postgresql.JSONB, nullable=True),
        sa.Column("output_json", postgresql.JSONB, nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("execution_time_ms", sa.Float, server_default="0"),
        sa.Column("version", sa.String(16), nullable=False, server_default="1.0.0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_skill_invocations_skill_id", "skill_invocations", ["skill_id"])
    op.create_index("ix_skill_invocations_agent_type", "skill_invocations", ["agent_type"])
    op.create_index("ix_skill_invocations_status", "skill_invocations", ["status"])
    op.create_index("ix_skill_invocations_created_at", "skill_invocations", ["created_at"])

    # --- learned_lessons ---
    op.create_table(
        "learned_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_runs.id"),
            nullable=True,
        ),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("related_order_ids", postgresql.JSONB, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("applied", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_lessons_category", "learned_lessons", ["category"])
    op.create_index("ix_lessons_severity", "learned_lessons", ["severity"])
    op.create_index("ix_lessons_created_at", "learned_lessons", ["created_at"])
    op.create_index("ix_lessons_applied", "learned_lessons", ["applied"])


def downgrade() -> None:
    op.drop_table("learned_lessons")
    op.drop_table("skill_invocations")
    op.drop_table("agent_runs")
    op.drop_table("skill_definitions")

"""Initial schema - all core tables.

Revision ID: 001
Revises: None
Create Date: 2024-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(256), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="VIEWER"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- Strategies ---
    op.create_table(
        "strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PAUSED"),
        sa.Column("trading_mode", sa.String(8), nullable=False, server_default="PAPER"),
        sa.Column("config_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_strategies_status", "strategies", ["status"])

    # --- Orders ---
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_order_id", sa.String(64), unique=True, nullable=False),
        sa.Column("exchange_order_id", sa.String(128), nullable=True),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("strategies.id"), nullable=True),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=True),
        sa.Column("stop_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("time_in_force", sa.String(8), server_default="GTC"),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("trading_mode", sa.String(8), nullable=False, server_default="PAPER"),
        sa.Column("filled_quantity", sa.Numeric(28, 12), server_default="0"),
        sa.Column("avg_fill_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("reject_reason", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_trading_mode", "orders", ["trading_mode"])
    op.create_index("ix_orders_exchange", "orders", ["exchange"])
    op.create_index("ix_orders_strategy_id", "orders", ["strategy_id"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])

    # --- Order Fills ---
    op.create_table(
        "order_fills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("exchange_fill_id", sa.String(128), nullable=True),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=False),
        sa.Column("commission", sa.Numeric(28, 12), server_default="0"),
        sa.Column("commission_asset", sa.String(16), nullable=True),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_order_fills_order_id", "order_fills", ["order_id"])
    op.create_index("ix_order_fills_fill_time", "order_fills", ["fill_time"])

    # --- Positions ---
    op.create_table(
        "positions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(8), nullable=False, server_default="FLAT"),
        sa.Column("quantity", sa.Numeric(28, 12), server_default="0"),
        sa.Column("avg_entry_price", sa.Numeric(28, 12), server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(28, 12), server_default="0"),
        sa.Column("unrealized_pnl", sa.Numeric(28, 12), server_default="0"),
        sa.Column("total_commission", sa.Numeric(28, 12), server_default="0"),
        sa.Column("trading_mode", sa.String(8), nullable=False, server_default="PAPER"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("exchange", "symbol", "trading_mode", name="uq_position_key"),
    )
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_index("ix_positions_trading_mode", "positions", ["trading_mode"])

    # --- Position Snapshots ---
    op.create_table(
        "position_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("position_id", UUID(as_uuid=True), sa.ForeignKey("positions.id"), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 12), nullable=False),
        sa.Column("mark_price", sa.Numeric(28, 12), nullable=False),
        sa.Column("unrealized_pnl", sa.Numeric(28, 12), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(28, 12), nullable=False),
        sa.Column("total_equity", sa.Numeric(28, 12), nullable=False),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_position_snapshots_time", "position_snapshots", ["snapshot_time"])
    op.create_index("ix_position_snapshots_position_id", "position_snapshots", ["position_id"])

    # --- Risk Events ---
    op.create_table(
        "risk_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("check_name", sa.String(64), nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="INFO"),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_risk_events_order_id", "risk_events", ["order_id"])
    op.create_index("ix_risk_events_check_name", "risk_events", ["check_name"])
    op.create_index("ix_risk_events_evaluated_at", "risk_events", ["evaluated_at"])

    # --- Reconciliation Runs ---
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("run_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="RUNNING"),
        sa.Column("breaks_found", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recon_runs_exchange", "reconciliation_runs", ["exchange"])
    op.create_index("ix_recon_runs_started_at", "reconciliation_runs", ["started_at"])

    # --- Reconciliation Breaks ---
    op.create_table(
        "reconciliation_breaks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("reconciliation_runs.id"), nullable=False),
        sa.Column("break_type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("internal_value", JSONB, nullable=True),
        sa.Column("exchange_value", JSONB, nullable=True),
        sa.Column("resolution", sa.String(16), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_recon_breaks_run_id", "reconciliation_breaks", ["run_id"])

    # --- Audit Log ---
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("actor", sa.String(64), nullable=False, server_default="system"),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_action", "audit_log", ["action"])

    # --- Ticker Snapshots ---
    op.create_table(
        "ticker_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("bid", sa.Numeric(28, 12), nullable=False),
        sa.Column("ask", sa.Numeric(28, 12), nullable=False),
        sa.Column("last", sa.Numeric(28, 12), nullable=False),
        sa.Column("volume_24h", sa.Numeric(28, 12), server_default="0"),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ticker_snap_symbol_time", "ticker_snapshots", ["symbol", "snapshot_time"])


def downgrade() -> None:
    op.drop_table("ticker_snapshots")
    op.drop_table("audit_log")
    op.drop_table("reconciliation_breaks")
    op.drop_table("reconciliation_runs")
    op.drop_table("risk_events")
    op.drop_table("position_snapshots")
    op.drop_table("positions")
    op.drop_table("order_fills")
    op.drop_table("orders")
    op.drop_table("strategies")
    op.drop_table("users")

"""Add backtest_runs and generated_strategies tables.

Merges the two branch heads (002, 003) and adds:
- backtest_runs: persists backtest configurations and results
- generated_strategies: stores agent-generated strategy code

Revision ID: 004
Revises: 002, 003
Create Date: 2026-03-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: Union[str, Sequence[str]] = ("002", "003")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Backtest Runs ---
    op.create_table(
        "backtest_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("initial_capital", sa.Numeric(28, 12), nullable=False),
        sa.Column("status", sa.String(16), server_default="running"),
        sa.Column("strategy_params", JSONB, nullable=True),
        sa.Column("cost_model_name", sa.String(32), server_default="forex"),
        sa.Column("total_trades", sa.Integer, server_default="0"),
        sa.Column("total_bars", sa.Integer, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(28, 12), server_default="0"),
        sa.Column("gross_pnl", sa.Numeric(28, 12), server_default="0"),
        sa.Column("sharpe_ratio", sa.Numeric(12, 6), server_default="0"),
        sa.Column("max_drawdown_pct", sa.Numeric(12, 6), server_default="0"),
        sa.Column("win_rate", sa.Numeric(8, 6), server_default="0"),
        sa.Column("profit_factor", sa.Numeric(12, 6), server_default="0"),
        sa.Column("expectancy", sa.Numeric(28, 12), server_default="0"),
        sa.Column("total_commission", sa.Numeric(28, 12), server_default="0"),
        sa.Column("fee_drag_pct", sa.Numeric(12, 6), server_default="0"),
        sa.Column("trades_per_day", sa.Numeric(12, 4), server_default="0"),
        sa.Column("metrics_json", JSONB, nullable=True),
        sa.Column("equity_curve_json", JSONB, nullable=True),
        sa.Column("is_trustworthy", sa.Boolean, server_default="false"),
        sa.Column("trust_issues", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_backtest_strategy_type", "backtest_runs", ["strategy_type"])
    op.create_index("ix_backtest_symbol", "backtest_runs", ["symbol"])
    op.create_index("ix_backtest_created", "backtest_runs", ["created_at"])

    # --- Generated Strategies ---
    op.create_table(
        "generated_strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_code", sa.Text, nullable=False),
        sa.Column("params_schema", JSONB, nullable=True),
        sa.Column("default_params", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_by_agent_run_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_generated_strategies_name", "generated_strategies", ["name"])
    op.create_index("ix_generated_strategies_active", "generated_strategies", ["is_active"])


def downgrade() -> None:
    op.drop_table("generated_strategies")
    op.drop_table("backtest_runs")

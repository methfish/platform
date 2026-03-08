"""Add OHLCV bars table for candlestick data.

Revision ID: 003
Revises: 001
Create Date: 2024-01-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- OHLCV Bars ---
    op.create_table(
        "ohlcv_bars",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(28, 12), nullable=False),
        sa.Column("high", sa.Numeric(28, 12), nullable=False),
        sa.Column("low", sa.Numeric(28, 12), nullable=False),
        sa.Column("close", sa.Numeric(28, 12), nullable=False),
        sa.Column("volume", sa.Numeric(28, 12), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_volume", sa.Numeric(28, 12), server_default="0"),
        sa.Column("trades", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ohlcv_symbol_interval_time",
        "ohlcv_bars",
        ["symbol", "interval", "open_time"],
        unique=True,
    )
    op.create_index("ix_ohlcv_symbol", "ohlcv_bars", ["symbol"])
    op.create_index("ix_ohlcv_interval", "ohlcv_bars", ["interval"])
    op.create_index("ix_ohlcv_open_time", "ohlcv_bars", ["open_time"])


def downgrade() -> None:
    op.drop_table("ohlcv_bars")

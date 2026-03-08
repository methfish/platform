"""
Pydantic request/response schemas for position-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PositionResponse(BaseModel):
    """Single position detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    avg_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    trading_mode: str
    updated_at: datetime


class PositionListResponse(BaseModel):
    """Aggregated position list with PnL totals."""

    positions: list[PositionResponse]
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal

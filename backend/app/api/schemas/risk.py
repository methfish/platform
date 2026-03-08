"""
Pydantic request/response schemas for risk-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RiskStatusResponse(BaseModel):
    """Current risk engine state snapshot."""

    kill_switch_active: bool
    trading_mode: str
    checks_enabled: bool
    daily_loss: Decimal
    daily_loss_limit: Decimal
    open_positions_count: int
    gross_exposure: Decimal


class RiskEventResponse(BaseModel):
    """Single risk check evaluation event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: Optional[UUID] = None
    check_name: str
    result: str
    severity: str
    details_json: Optional[dict[str, Any]] = None
    evaluated_at: datetime


class RiskEventListResponse(BaseModel):
    """List of risk events."""

    events: list[RiskEventResponse]
    total: int

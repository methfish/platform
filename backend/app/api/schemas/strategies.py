"""
Pydantic request/response schemas for strategy-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrategyResponse(BaseModel):
    """Strategy detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    strategy_type: str
    status: str
    trading_mode: str
    config_json: Optional[dict[str, Any]] = None
    created_at: datetime


class StrategyListResponse(BaseModel):
    """List of strategies."""

    strategies: list[StrategyResponse]
    total: int


class StrategyActionRequest(BaseModel):
    """Request body for strategy enable/disable actions."""

    action: str = Field(
        ...,
        pattern="^(enable|disable)$",
        description="Action to perform: 'enable' or 'disable'",
    )

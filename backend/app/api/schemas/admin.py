"""
Pydantic request/response schemas for admin and system endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KillSwitchRequest(BaseModel):
    """Toggle the global kill switch."""

    activate: bool = Field(
        ..., description="True to activate kill switch, False to deactivate"
    )


class LiveModeConfirmRequest(BaseModel):
    """Operator confirmation for live trading mode."""

    confirm: bool = Field(..., description="Must be True to confirm")
    confirmation_phrase: str = Field(
        ...,
        description="Must be 'I CONFIRM LIVE TRADING' to proceed",
    )


class TradingModeResponse(BaseModel):
    """Current trading mode state."""

    mode: str
    live_enabled: bool
    operator_confirmed: bool
    kill_switch: bool


class SystemStatusResponse(BaseModel):
    """Overall system health status."""

    status: str = Field(..., examples=["healthy"])
    version: str
    environment: str
    trading_mode: str
    exchange_status: str
    db_status: str
    redis_status: str
    uptime: float = Field(..., description="Uptime in seconds")


class AuditLogResponse(BaseModel):
    """Single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    entity_id: str
    action: str
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    actor: str
    correlation_id: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    logs: list[AuditLogResponse]
    total: int

"""
Pydantic request/response schemas for reconciliation endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationRunResponse(BaseModel):
    """A single reconciliation run summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exchange: str
    run_type: str
    status: str
    breaks_found: int
    started_at: datetime
    completed_at: Optional[datetime] = None


class ReconciliationBreakResponse(BaseModel):
    """A single reconciliation break (discrepancy)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    break_type: str
    symbol: Optional[str] = None
    internal_value: Optional[dict[str, Any]] = None
    exchange_value: Optional[dict[str, Any]] = None
    resolution: Optional[str] = None


class ReconciliationRunDetailResponse(BaseModel):
    """A run with its breaks included."""

    run: ReconciliationRunResponse
    breaks: list[ReconciliationBreakResponse]


class ReconciliationRunListResponse(BaseModel):
    """Paginated list of reconciliation runs."""

    runs: list[ReconciliationRunResponse]
    total: int


class ReconciliationTriggerRequest(BaseModel):
    """Request to trigger a manual reconciliation run."""

    exchange: str = Field(..., min_length=1, max_length=32, examples=["binance_spot"])

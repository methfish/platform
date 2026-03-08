"""
Reconciliation endpoints.

POST /reconciliation/run             - Trigger a manual reconciliation run.
GET  /reconciliation/runs            - List reconciliation runs.
GET  /reconciliation/runs/{run_id}   - Get a run with its breaks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.reconciliation import (
    ReconciliationBreakResponse,
    ReconciliationRunDetailResponse,
    ReconciliationRunListResponse,
    ReconciliationRunResponse,
    ReconciliationTriggerRequest,
)
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.core.enums import ReconciliationStatus, UserRole
from app.core.exceptions import PensyError, ReconciliationError
from app.db.session import get_session
from app.models.reconciliation import ReconciliationBreak, ReconciliationRun
from app.models.user import User

logger = logging.getLogger("pensy.api.reconciliation")

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post(
    "/run",
    response_model=ReconciliationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a manual reconciliation run",
)
async def trigger_reconciliation(
    body: ReconciliationTriggerRequest,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
) -> ReconciliationRunResponse:
    """
    Create a new reconciliation run record and (in a full implementation)
    kick off the reconciliation process asynchronously.
    """
    run = ReconciliationRun(
        exchange=body.exchange,
        run_type="MANUAL",
        status=ReconciliationStatus.RUNNING.value,
        breaks_found=0,
        started_at=datetime.now(timezone.utc),
    )

    session.add(run)
    await session.flush()
    await session.refresh(run)

    logger.info(
        "Reconciliation run %s triggered for %s by %s",
        run.id,
        body.exchange,
        current_user.username,
    )

    # TODO: Dispatch to reconciliation service
    # await recon_service.run(run)

    return ReconciliationRunResponse.model_validate(run)


@router.get(
    "/runs",
    response_model=ReconciliationRunListResponse,
    summary="List reconciliation runs",
)
async def list_runs(
    exchange: Optional[str] = Query(None, description="Filter by exchange"),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReconciliationRunListResponse:
    """Return paginated list of reconciliation runs."""
    query = select(ReconciliationRun)

    if exchange:
        query = query.where(ReconciliationRun.exchange == exchange)
    if status_filter:
        query = query.where(ReconciliationRun.status == status_filter.upper())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = (
        query.order_by(ReconciliationRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    runs = result.scalars().all()

    return ReconciliationRunListResponse(
        runs=[ReconciliationRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get(
    "/runs/{run_id}",
    response_model=ReconciliationRunDetailResponse,
    summary="Get reconciliation run detail with breaks",
)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReconciliationRunDetailResponse:
    """Return a single reconciliation run with all its breaks."""
    result = await session.execute(
        select(ReconciliationRun).where(ReconciliationRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise ReconciliationError(
            f"Reconciliation run not found: {run_id}",
            code="RECON_RUN_NOT_FOUND",
        )

    break_result = await session.execute(
        select(ReconciliationBreak).where(ReconciliationBreak.run_id == run_id)
    )
    breaks = break_result.scalars().all()

    return ReconciliationRunDetailResponse(
        run=ReconciliationRunResponse.model_validate(run),
        breaks=[ReconciliationBreakResponse.model_validate(b) for b in breaks],
    )

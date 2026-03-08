"""
Risk management endpoints.

GET  /risk/status       - Current risk engine state.
GET  /risk/events       - Recent risk evaluation events.
POST /risk/kill-switch  - Toggle the global kill switch.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.admin import KillSwitchRequest
from app.api.schemas.risk import RiskEventListResponse, RiskEventResponse, RiskStatusResponse
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.config import Settings, get_settings
from app.core.enums import TradingMode, UserRole
from app.db.session import get_session
from app.dependencies import TradingState, get_trading_state, is_live_trading_active
from app.models.position import Position
from app.models.risk import RiskEvent
from app.models.user import User

logger = logging.getLogger("pensy.api.risk")

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get(
    "/status",
    response_model=RiskStatusResponse,
    summary="Get current risk engine status",
)
async def risk_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> RiskStatusResponse:
    """
    Return the current risk engine snapshot including kill switch state,
    trading mode, daily loss, and exposure metrics.
    """
    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER

    # Count open positions
    pos_count_result = await session.execute(
        select(func.count())
        .select_from(Position)
        .where(Position.quantity != Decimal("0"))
        .where(Position.trading_mode == mode.value)
    )
    open_positions_count = pos_count_result.scalar_one()

    # Gross exposure (sum of |quantity * avg_entry_price|)
    exposure_result = await session.execute(
        select(func.coalesce(func.sum(func.abs(Position.quantity * Position.avg_entry_price)), 0))
        .where(Position.quantity != Decimal("0"))
        .where(Position.trading_mode == mode.value)
    )
    gross_exposure = exposure_result.scalar_one()

    # Sum daily realized losses (placeholder: sum all negative realized_pnl)
    loss_result = await session.execute(
        select(
            func.coalesce(
                func.sum(func.abs(Position.realized_pnl)),
                0,
            )
        )
        .where(Position.realized_pnl < 0)
        .where(Position.trading_mode == mode.value)
    )
    daily_loss = loss_result.scalar_one()

    return RiskStatusResponse(
        kill_switch_active=state.kill_switch_active,
        trading_mode=mode.value,
        checks_enabled=True,
        daily_loss=daily_loss,
        daily_loss_limit=settings.MAX_DAILY_LOSS,
        open_positions_count=open_positions_count,
        gross_exposure=gross_exposure,
    )


@router.get(
    "/events",
    response_model=RiskEventListResponse,
    summary="List recent risk evaluation events",
)
async def list_risk_events(
    check_name: Optional[str] = Query(None, description="Filter by check name"),
    result_filter: Optional[str] = Query(None, alias="result", description="PASS/FAIL/WARN"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RiskEventListResponse:
    """Return paginated risk events with optional filters."""
    query = select(RiskEvent)

    if check_name:
        query = query.where(RiskEvent.check_name == check_name)
    if result_filter:
        query = query.where(RiskEvent.result == result_filter.upper())

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(RiskEvent.evaluated_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    events = result.scalars().all()

    return RiskEventListResponse(
        events=[RiskEventResponse.model_validate(e) for e in events],
        total=total,
    )


@router.post(
    "/kill-switch",
    response_model=RiskStatusResponse,
    summary="Toggle the global kill switch",
)
async def toggle_kill_switch(
    body: KillSwitchRequest,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> RiskStatusResponse:
    """
    Activate or deactivate the global kill switch. When active, all new
    orders are blocked. Requires OPERATOR role or above.
    """
    state.kill_switch_active = body.activate

    action = "ACTIVATED" if body.activate else "DEACTIVATED"
    logger.warning(
        "Kill switch %s by %s", action, current_user.username
    )

    # Return updated risk status by delegating to the status endpoint logic
    return await risk_status(
        current_user=current_user,
        session=session,
        settings=settings,
        state=state,
    )

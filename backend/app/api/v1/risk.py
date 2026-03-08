"""
Risk management endpoints.

GET  /risk/status       - Current risk engine state.
GET  /risk/events       - Recent risk evaluation events.
POST /risk/kill-switch  - Toggle the global kill switch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.admin import KillSwitchRequest
from app.api.schemas.risk import RiskEventListResponse, RiskEventResponse, RiskStatusResponse, RiskMonitoringDashboard, RiskLimitStatus
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.config import Settings, get_settings
from app.core.enums import TradingMode, UserRole
from app.db.session import get_session
from app.dependencies import TradingState, get_trading_state, is_live_trading_active
from app.models.order import Order
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


@router.get(
    "/monitoring-dashboard",
    response_model=RiskMonitoringDashboard,
    summary="Real-time risk monitoring dashboard for live trading",
)
async def risk_monitoring_dashboard(
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> RiskMonitoringDashboard:
    """
    Comprehensive risk monitoring dashboard showing:
    - Real-time risk limit status
    - Daily loss tracking
    - Position exposure
    - Trade performance metrics
    - Recent risk events
    - System health checks

    Designed for live trading oversight.
    """
    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER

    # --- Get Risk Status Baseline ---
    pos_count_result = await session.execute(
        select(func.count())
        .select_from(Position)
        .where(Position.quantity != Decimal("0"))
        .where(Position.trading_mode == mode.value)
    )
    open_positions_count = pos_count_result.scalar_one()

    exposure_result = await session.execute(
        select(func.coalesce(func.sum(func.abs(Position.quantity * Position.avg_entry_price)), 0))
        .where(Position.quantity != Decimal("0"))
        .where(Position.trading_mode == mode.value)
    )
    gross_exposure = Decimal(str(exposure_result.scalar_one() or 0))

    loss_result = await session.execute(
        select(func.coalesce(func.sum(func.abs(Position.realized_pnl)), 0))
        .where(Position.realized_pnl < 0)
        .where(Position.trading_mode == mode.value)
    )
    daily_loss = Decimal(str(loss_result.scalar_one() or 0))

    # --- Get Trade Performance Metrics ---
    total_trades_result = await session.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.status == "FILLED")
        .where(Order.trading_mode == mode.value)
    )
    total_trades = total_trades_result.scalar_one() or 0

    winning_trades_result = await session.execute(
        select(func.count())
        .select_from(Position)
        .where(Position.realized_pnl > 0)
        .where(Position.trading_mode == mode.value)
    )
    winning_trades = winning_trades_result.scalar_one() or 0

    losing_trades_result = await session.execute(
        select(func.count())
        .select_from(Position)
        .where(Position.realized_pnl < 0)
        .where(Position.trading_mode == mode.value)
    )
    losing_trades = losing_trades_result.scalar_one() or 0

    win_rate = (winning_trades / (winning_trades + losing_trades) * 100) if (winning_trades + losing_trades) > 0 else 0.0

    # --- Build Limit Status Breakdown ---
    max_exposure = settings.MAX_GROSS_EXPOSURE
    max_daily_loss = settings.MAX_DAILY_LOSS
    max_open_orders = settings.MAX_OPEN_ORDERS

    # Daily Loss Status
    daily_loss_pct = float(daily_loss / max_daily_loss * 100) if max_daily_loss > 0 else 0.0
    if daily_loss_pct >= 100:
        daily_loss_status = "CRITICAL"
    elif daily_loss_pct >= 80:
        daily_loss_status = "WARNING"
    else:
        daily_loss_status = "OK"

    # Exposure Status
    exposure_pct = float(gross_exposure / max_exposure * 100) if max_exposure > 0 else 0.0
    if exposure_pct >= 100:
        exposure_status = "CRITICAL"
    elif exposure_pct >= 80:
        exposure_status = "WARNING"
    else:
        exposure_status = "OK"

    # Positions Status
    if open_positions_count >= max_open_orders:
        positions_status = "CRITICAL"
    elif open_positions_count >= int(max_open_orders * 0.8):
        positions_status = "WARNING"
    else:
        positions_status = "OK"

    # Build limit statuses list
    limit_statuses = [
        RiskLimitStatus(
            name="Daily Loss",
            current_value=daily_loss,
            limit_value=max_daily_loss,
            percentage_used=daily_loss_pct,
            status=daily_loss_status,
            message=f"${daily_loss:.2f} of ${max_daily_loss:.2f} ({daily_loss_pct:.1f}%)",
        ),
        RiskLimitStatus(
            name="Gross Exposure",
            current_value=gross_exposure,
            limit_value=max_exposure,
            percentage_used=exposure_pct,
            status=exposure_status,
            message=f"${gross_exposure:.2f} of ${max_exposure:.2f} ({exposure_pct:.1f}%)",
        ),
        RiskLimitStatus(
            name="Open Orders",
            current_value=Decimal(str(open_positions_count)),
            limit_value=Decimal(str(max_open_orders)),
            percentage_used=float(open_positions_count / max_open_orders * 100) if max_open_orders > 0 else 0.0,
            status=positions_status,
            message=f"{open_positions_count} of {max_open_orders} orders",
        ),
    ]

    # --- Get Recent Risk Events ---
    recent_events_result = await session.execute(
        select(RiskEvent)
        .order_by(RiskEvent.evaluated_at.desc())
        .limit(10)
    )
    recent_events = recent_events_result.scalars().all()
    recent_risk_events = [RiskEventResponse.model_validate(e) for e in recent_events]

    # --- Health Checks ---
    exchange_healthy = True  # Placeholder - would check actual exchange status
    database_responsive = True  # We got this far, so DB is responsive
    price_data_stale = False  # Placeholder - would check price freshness

    return RiskMonitoringDashboard(
        timestamp=datetime.now(timezone.utc),
        trading_mode=mode.value,
        kill_switch_active=state.kill_switch_active,
        checks_enabled=True,
        daily_loss=daily_loss,
        daily_loss_limit=max_daily_loss,
        daily_loss_status=daily_loss_status,
        gross_exposure=gross_exposure,
        max_exposure=max_exposure,
        exposure_status=exposure_status,
        open_positions_count=open_positions_count,
        max_open_orders=max_open_orders,
        positions_status=positions_status,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        limit_statuses=limit_statuses,
        recent_risk_events=recent_risk_events,
        exchange_healthy=exchange_healthy,
        database_responsive=database_responsive,
        price_data_stale=price_data_stale,
    )

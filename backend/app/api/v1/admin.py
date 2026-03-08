"""
Admin, health, metrics, and system management endpoints.

GET  /health                - Health check (no auth required).
GET  /metrics               - Prometheus-format metrics placeholder.
GET  /exchanges/status      - Exchange connectivity status.
POST /admin/live-mode-confirm - Operator confirms live trading.
GET  /admin/trading-mode    - Current trading mode info.
GET  /audit-logs            - List audit log entries.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.admin import (
    AuditLogListResponse,
    AuditLogResponse,
    LiveModeConfirmRequest,
    SystemStatusResponse,
    TradingModeResponse,
)
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.config import Settings, get_settings
from app.core.enums import TradingMode, UserRole
from app.core.exceptions import PensyError, TradingModeError
from app.db.session import get_session
from app.dependencies import TradingState, get_trading_state, is_live_trading_active
from app.models.audit import AuditLog
from app.models.user import User

logger = logging.getLogger("pensy.api.admin")

router = APIRouter(tags=["admin"])

# Track server startup for uptime calculation
_start_time = time.monotonic()


@router.get(
    "/health",
    response_model=SystemStatusResponse,
    summary="System health check",
)
async def health_check(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> SystemStatusResponse:
    """
    Return overall system health. No authentication required so external
    monitors can probe the endpoint.
    """
    # Database health
    db_status = "healthy"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Exchange status placeholder
    exchange_status = "connected"
    try:
        from app.dependencies import get_exchange_adapter
        adapter = get_exchange_adapter()
        exchange_status = "connected" if adapter.is_connected else "disconnected"
    except RuntimeError:
        exchange_status = "not_initialized"

    # Redis status placeholder
    redis_status = "unknown"

    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER

    return SystemStatusResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        version="0.1.0",
        environment=settings.APP_ENV.value,
        trading_mode=mode.value,
        exchange_status=exchange_status,
        db_status=db_status,
        redis_status=redis_status,
        uptime=time.monotonic() - _start_time,
    )


@router.get(
    "/metrics",
    summary="Prometheus metrics endpoint (placeholder)",
)
async def metrics(
    current_user: User = Depends(get_current_user),
) -> Response:
    """
    Return Prometheus-compatible metrics. This is a placeholder that returns
    basic counters; a full implementation would use prometheus_client.
    """
    uptime = time.monotonic() - _start_time
    body = (
        "# HELP pensy_uptime_seconds Server uptime in seconds\n"
        "# TYPE pensy_uptime_seconds gauge\n"
        f"pensy_uptime_seconds {uptime:.2f}\n"
    )
    return Response(content=body, media_type="text/plain; charset=utf-8")


@router.get(
    "/exchanges/status",
    summary="Exchange connectivity status",
)
async def exchange_status(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return connectivity status for all configured exchanges."""
    try:
        from app.dependencies import get_exchange_adapter
        adapter = get_exchange_adapter()
        return {
            "exchanges": [
                {
                    "name": adapter.exchange_name,
                    "connected": adapter.is_connected,
                    "is_paper": adapter.is_paper,
                }
            ]
        }
    except RuntimeError:
        return {"exchanges": [], "message": "No exchange adapter initialized"}


@router.post(
    "/admin/live-mode-confirm",
    response_model=TradingModeResponse,
    summary="Operator confirms live trading mode",
)
async def confirm_live_mode(
    body: LiveModeConfirmRequest,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> TradingModeResponse:
    """
    Confirm live trading mode. Requires:
    1. LIVE_TRADING_ENABLED=true in environment.
    2. confirm=True in the request body.
    3. confirmation_phrase == 'I CONFIRM LIVE TRADING'.

    This is the second gate in the two-key mechanism for live trading.
    """
    if not settings.LIVE_TRADING_ENABLED:
        raise TradingModeError(
            "LIVE_TRADING_ENABLED is not set to true in environment configuration"
        )

    if not body.confirm:
        raise TradingModeError("confirm must be True")

    if body.confirmation_phrase != "I CONFIRM LIVE TRADING":
        raise TradingModeError(
            "Confirmation phrase must be exactly 'I CONFIRM LIVE TRADING'"
        )

    state.operator_confirmed_live = True

    logger.warning(
        "LIVE TRADING CONFIRMED by operator %s", current_user.username
    )

    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER
    return TradingModeResponse(
        mode=mode.value,
        live_enabled=settings.LIVE_TRADING_ENABLED,
        operator_confirmed=state.operator_confirmed_live,
        kill_switch=state.kill_switch_active,
    )


@router.get(
    "/admin/trading-mode",
    response_model=TradingModeResponse,
    summary="Get current trading mode information",
)
async def trading_mode(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> TradingModeResponse:
    """Return the current trading mode configuration and state."""
    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER
    return TradingModeResponse(
        mode=mode.value,
        live_enabled=settings.LIVE_TRADING_ENABLED,
        operator_confirmed=state.operator_confirmed_live,
        kill_switch=state.kill_switch_active,
    )


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="List audit log entries",
)
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Filter by audit action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
) -> AuditLogListResponse:
    """Return paginated audit log entries. Requires OPERATOR role."""
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
    )

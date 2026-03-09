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
    SwitchExchangeRequest,
    SwitchExchangeResponse,
    SystemStatusResponse,
    TradingModeResponse,
)
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.config import Settings, get_settings
from app.core.enums import ExchangeName, TradingMode, UserRole
from app.core.exceptions import PensyError, TradingModeError
from app.db.session import get_session
from app.dependencies import TradingState, get_trading_state, is_live_trading_active, set_exchange_adapter
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


EXCHANGE_NAME_MAP = {
    "binance_spot": ExchangeName.BINANCE_SPOT,
    "binance_futures": ExchangeName.BINANCE_FUTURES,
    "paper": ExchangeName.PAPER,
}


@router.post(
    "/admin/switch-exchange",
    response_model=SwitchExchangeResponse,
    summary="Switch the active exchange adapter at runtime",
)
async def switch_exchange(
    body: SwitchExchangeRequest,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> SwitchExchangeResponse:
    """
    Hot-swap the exchange adapter. Requires OPERATOR role.

    For live exchanges (non-paper), LIVE_TRADING_ENABLED must be true
    and the operator must have confirmed live mode first.

    Steps: disconnect old adapter → create new adapter → connect → set global.
    """
    if body.confirmation_phrase != "I CONFIRM EXCHANGE SWITCH":
        raise TradingModeError(
            "Confirmation phrase must be exactly 'I CONFIRM EXCHANGE SWITCH'"
        )

    exchange_enum = EXCHANGE_NAME_MAP.get(body.exchange)
    if exchange_enum is None:
        raise PensyError(
            f"Unknown exchange '{body.exchange}'. "
            f"Valid options: {', '.join(EXCHANGE_NAME_MAP.keys())}"
        )

    # Safety: switching to a live exchange requires live trading to be active
    is_live = exchange_enum not in (ExchangeName.PAPER,)
    if is_live and not is_live_trading_active(settings, state):
        raise TradingModeError(
            "Cannot switch to a live exchange without enabling and confirming live trading first. "
            "Set LIVE_TRADING_ENABLED=true and call POST /admin/live-mode-confirm."
        )

    trading_mode = TradingMode.LIVE if is_live else TradingMode.PAPER

    # Disconnect old adapter
    from app.dependencies import get_exchange_adapter
    try:
        old_adapter = get_exchange_adapter()
        await old_adapter.disconnect()
        logger.info("Disconnected old adapter: %s", old_adapter.exchange_name)
    except RuntimeError:
        pass  # No adapter was initialized

    # Create and connect new adapter
    from app.exchange.factory import create_exchange_adapter
    new_adapter = create_exchange_adapter(exchange_enum, settings, trading_mode)
    await new_adapter.connect()
    set_exchange_adapter(new_adapter)

    logger.warning(
        "Exchange switched to %s by operator %s",
        new_adapter.exchange_name,
        current_user.username,
    )

    return SwitchExchangeResponse(
        success=True,
        exchange_name=new_adapter.exchange_name,
        is_paper=new_adapter.is_paper,
        is_connected=new_adapter.is_connected,
        message=f"Switched to {new_adapter.exchange_name} successfully",
    )

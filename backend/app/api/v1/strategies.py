"""
Strategy management endpoints.

GET  /strategies                      - List all strategies.
POST /strategies/{strategy_id}/enable  - Enable a strategy.
POST /strategies/{strategy_id}/disable - Disable a strategy.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.strategies import StrategyListResponse, StrategyResponse
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.core.enums import StrategyStatus, UserRole
from app.core.exceptions import PensyError, StrategyError
from app.db.session import get_session
from app.models.strategy import Strategy
from app.models.user import User

logger = logging.getLogger("pensy.api.strategies")

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get(
    "",
    response_model=StrategyListResponse,
    summary="List all registered strategies",
)
async def list_strategies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StrategyListResponse:
    """Return all strategies regardless of status."""
    count_result = await session.execute(select(func.count()).select_from(Strategy))
    total = count_result.scalar_one()

    result = await session.execute(
        select(Strategy).order_by(Strategy.name)
    )
    strategies = result.scalars().all()

    return StrategyListResponse(
        strategies=[StrategyResponse.model_validate(s) for s in strategies],
        total=total,
    )


@router.post(
    "/{strategy_id}/enable",
    response_model=StrategyResponse,
    summary="Enable a strategy",
)
async def enable_strategy(
    strategy_id: UUID,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """
    Set a strategy's status to ACTIVE. Requires OPERATOR role or above.
    """
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if strategy is None:
        raise StrategyError(f"Strategy not found: {strategy_id}", code="STRATEGY_NOT_FOUND")

    if strategy.status == StrategyStatus.ACTIVE.value:
        raise StrategyError("Strategy is already active", code="STRATEGY_ALREADY_ACTIVE")

    strategy.status = StrategyStatus.ACTIVE.value
    await session.flush()
    await session.refresh(strategy)

    logger.info(
        "Strategy %s enabled by %s", strategy.name, current_user.username
    )
    return StrategyResponse.model_validate(strategy)


@router.post(
    "/{strategy_id}/disable",
    response_model=StrategyResponse,
    summary="Disable a strategy",
)
async def disable_strategy(
    strategy_id: UUID,
    current_user: User = Depends(require_role(UserRole.OPERATOR)),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """
    Set a strategy's status to PAUSED. Requires OPERATOR role or above.
    """
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if strategy is None:
        raise StrategyError(f"Strategy not found: {strategy_id}", code="STRATEGY_NOT_FOUND")

    if strategy.status == StrategyStatus.PAUSED.value:
        raise StrategyError("Strategy is already paused", code="STRATEGY_ALREADY_PAUSED")

    strategy.status = StrategyStatus.PAUSED.value
    await session.flush()
    await session.refresh(strategy)

    logger.info(
        "Strategy %s disabled by %s", strategy.name, current_user.username
    )
    return StrategyResponse.model_validate(strategy)

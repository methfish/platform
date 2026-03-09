"""
Strategy engine API endpoints.

CRUD for strategies + start/stop/status for the MM/Arb runner.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.strategy_engine import (
    CreateStrategyRequest,
    StrategyPnLResponse,
    StrategyResponse,
    StrategyRuntimeStatus,
    UpdateStrategyConfigRequest,
)
from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.core.enums import StrategyStatus, UserRole
from app.db.session import get_session
from app.dependencies import get_mm_arb_runner
from app.models.strategy import Strategy
from app.models.user import User
from app.strategy.configs import validate_strategy_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-engine", tags=["strategy-engine"])


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """Create a new strategy with validated config_json."""
    # Validate config
    try:
        validate_strategy_config(body.strategy_type, body.config_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid config: {exc}",
        )

    # Check uniqueness
    existing = await session.execute(
        select(Strategy).where(Strategy.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Strategy '{body.name}' already exists",
        )

    strategy = Strategy(
        name=body.name,
        description=body.description,
        strategy_type=body.strategy_type,
        status=StrategyStatus.PAUSED.value,
        trading_mode=body.trading_mode,
        config_json=body.config_json,
    )
    session.add(strategy)
    await session.flush()

    logger.info("Strategy created: %s (type=%s)", body.name, body.strategy_type)
    return StrategyResponse.model_validate(strategy)


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[StrategyResponse]:
    """List all strategies."""
    result = await session.execute(
        select(Strategy).order_by(Strategy.created_at.desc())
    )
    strategies = result.scalars().all()
    return [StrategyResponse.model_validate(s) for s in strategies]


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """Get a single strategy by ID."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return StrategyResponse.model_validate(strategy)


@router.post("/{strategy_id}/start", response_model=StrategyRuntimeStatus)
async def start_strategy(
    strategy_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> StrategyRuntimeStatus:
    """Start a strategy as a background task."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if strategy.status == StrategyStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="Strategy is already running")

    runner = get_mm_arb_runner()

    try:
        result = await runner.start_strategy(
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
            config=strategy.config_json or {},
            strategy_db_id=strategy.id,
            trading_mode=strategy.trading_mode,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start strategy: {exc}",
        )

    return StrategyRuntimeStatus(**result)


@router.post("/{strategy_id}/stop", response_model=StrategyRuntimeStatus)
async def stop_strategy(
    strategy_id: UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> StrategyRuntimeStatus:
    """Stop a running strategy."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    runner = get_mm_arb_runner()

    try:
        result = await runner.stop_strategy(strategy.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return StrategyRuntimeStatus(**result)


@router.get("/{strategy_id}/status", response_model=StrategyRuntimeStatus)
async def get_strategy_status(
    strategy_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StrategyRuntimeStatus:
    """Get real-time strategy status including P&L."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    runner = get_mm_arb_runner()

    try:
        result = runner.get_runtime_status(strategy.name)
    except Exception:
        # Strategy not running, return DB status
        return StrategyRuntimeStatus(
            name=strategy.name,
            status=strategy.status,
            strategy_type=strategy.strategy_type,
        )

    return StrategyRuntimeStatus(**result)


@router.get("/{strategy_id}/pnl", response_model=StrategyPnLResponse)
async def get_strategy_pnl(
    strategy_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StrategyPnLResponse:
    """Get detailed P&L breakdown."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    runner = get_mm_arb_runner()
    pnl_data = runner._strategy_pnl.get(strategy.name)

    if not pnl_data:
        return StrategyPnLResponse(strategy_name=strategy.name)

    return StrategyPnLResponse(**pnl_data.to_dict())


@router.put("/{strategy_id}/config", response_model=StrategyResponse)
async def update_strategy_config(
    strategy_id: UUID,
    body: UpdateStrategyConfigRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """Update config for a paused strategy."""
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if strategy.status == StrategyStatus.ACTIVE.value:
        raise HTTPException(
            status_code=409,
            detail="Cannot update config while strategy is running. Stop it first.",
        )

    # Validate new config
    try:
        validate_strategy_config(strategy.strategy_type, body.config_json)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid config: {exc}",
        )

    strategy.config_json = body.config_json
    await session.flush()

    return StrategyResponse.model_validate(strategy)

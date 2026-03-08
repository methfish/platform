"""
Position and PnL endpoints.

GET /positions - List current positions.
GET /pnl       - Aggregated PnL summary.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.positions import PositionListResponse, PositionResponse
from app.auth.jwt import get_current_user
from app.db.session import get_session
from app.models.position import Position
from app.models.user import User

logger = logging.getLogger("pensy.api.positions")

router = APIRouter(tags=["positions"])


@router.get(
    "/positions",
    response_model=PositionListResponse,
    summary="List current positions",
)
async def list_positions(
    trading_mode: Optional[str] = Query(None, description="PAPER or LIVE"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PositionListResponse:
    """
    Return all current positions, optionally filtered by trading mode or
    symbol. Includes aggregated unrealized and realized PnL.
    """
    query = select(Position).where(Position.quantity != Decimal("0"))

    if trading_mode:
        query = query.where(Position.trading_mode == trading_mode.upper())
    if symbol:
        query = query.where(Position.symbol == symbol.upper())

    result = await session.execute(query.order_by(Position.symbol))
    positions = result.scalars().all()

    total_unrealized = sum(p.unrealized_pnl for p in positions)
    total_realized = sum(p.realized_pnl for p in positions)

    return PositionListResponse(
        positions=[PositionResponse.model_validate(p) for p in positions],
        total_unrealized_pnl=total_unrealized,
        total_realized_pnl=total_realized,
    )


@router.get(
    "/pnl",
    response_model=PositionListResponse,
    summary="Get PnL summary across all positions",
)
async def get_pnl(
    trading_mode: Optional[str] = Query(None, description="PAPER or LIVE"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PositionListResponse:
    """
    Return PnL summary across all positions (including flat positions with
    historical realized PnL).
    """
    query = select(Position)

    if trading_mode:
        query = query.where(Position.trading_mode == trading_mode.upper())

    result = await session.execute(query.order_by(Position.symbol))
    positions = result.scalars().all()

    total_unrealized = sum(p.unrealized_pnl for p in positions)
    total_realized = sum(p.realized_pnl for p in positions)

    return PositionListResponse(
        positions=[PositionResponse.model_validate(p) for p in positions],
        total_unrealized_pnl=total_unrealized,
        total_realized_pnl=total_realized,
    )

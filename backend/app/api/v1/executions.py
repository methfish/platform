"""Order management endpoints."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.auth.permissions import require_role
from app.config import Settings, get_settings
from app.core.enums import UserRole
from app.db.session import get_session
from app.dependencies import TradingState, get_trading_state, is_live_trading_active
from app.models.order import Order, OrderFill
from app.models.position import Position
from app.models.user import User
from app.api.schemas.orders import OrderCreateRequest, OrderResponse, OrderListResponse
from app.oms.executor import OrderExecutor
from app.position.manager import PositionManager
from app.exchange.binance.client import BinanceRestClient
from app.exchange.binance.auth import BinanceAuth

logger = logging.getLogger("pensy.api.orders")

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_executor(
    settings: Settings = Depends(get_settings),
) -> OrderExecutor:
    """Get order executor (paper or live depending on settings)."""
    binance_client = None
    if is_live_trading_active(settings, None):
        auth = BinanceAuth(
            api_key=settings.BINANCE_API_KEY.get_secret_value(),
            api_secret=settings.BINANCE_API_SECRET.get_secret_value(),
        )
        binance_client = BinanceRestClient(
            auth=auth,
            testnet=settings.BINANCE_TESTNET,
        )
    return OrderExecutor(binance_client=binance_client, settings=settings)


@router.post(
    "/place",
    response_model=OrderResponse,
    summary="Place a new order",
)
async def place_order(
    request: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
    executor: OrderExecutor = Depends(get_order_executor),
) -> OrderResponse:
    """
    Place a new order.

    - Can be MARKET or LIMIT
    - LIMIT orders require a price
    - Returns immediately (fills are async)
    """
    trading_mode = "LIVE" if is_live_trading_active(settings, state) else "PAPER"

    try:
        order = await executor.place_order(
            session=session,
            symbol=request.symbol,
            side=request.side.value,
            order_type=request.order_type.value,
            quantity=request.quantity,
            price=request.price,
            trading_mode=trading_mode,
        )
        return OrderResponse.model_validate(order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to place order: {e}")
        raise HTTPException(status_code=500, detail="Failed to place order")


@router.get(
    "/",
    response_model=OrderListResponse,
    summary="List orders",
)
async def list_orders(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    """Get paginated list of recent orders."""
    query = select(Order)

    if symbol:
        query = query.where(Order.symbol == symbol.upper())
    if status:
        query = query.where(Order.status == status.upper())

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(Order.select(*query.add_columns()))
    )
    total = count_result.scalar_one()

    # Paginate
    query = query.order_by(desc(Order.created_at)).limit(limit).offset(offset)
    result = await session.execute(query)
    orders = result.scalars().all()

    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=total,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Get full details of a single order including fills."""
    result = await session.execute(
        select(Order).where(Order.client_order_id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse.model_validate(order)


@router.delete(
    "/{order_id}",
    response_model=dict,
    summary="Cancel an order",
)
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    executor: OrderExecutor = Depends(get_order_executor),
) -> dict:
    """Cancel a pending order."""
    result = await session.execute(
        select(Order).where(Order.client_order_id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in ("PENDING",):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel {order.status} order",
        )

    success = await executor.cancel_order(session, order)
    await session.commit()

    return {
        "success": success,
        "order_id": order.client_order_id,
        "status": order.status,
    }


@router.get(
    "/positions/all",
    response_model=list[dict],
    summary="Get all open positions",
)
async def get_positions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get all open positions."""
    result = await session.execute(
        select(Position).where(Position.quantity != Decimal("0"))
    )
    positions = result.scalars().all()

    return [
        {
            "symbol": p.symbol,
            "side": p.side,
            "quantity": str(p.quantity),
            "entry_price": str(p.avg_entry_price),
            "realized_pnl": str(p.realized_pnl),
        }
        for p in positions
    ]


# Import for count
from sqlalchemy import func

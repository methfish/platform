"""
Order management endpoints.

GET  /orders              - List orders with optional filters.
POST /orders              - Submit a new order via the OMS.
GET  /orders/{order_id}   - Retrieve a single order.
POST /orders/{order_id}/cancel - Request cancellation.
GET  /fills               - List recent order fills.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.orders import (
    FillResponse,
    OrderCreateRequest,
    OrderListResponse,
    OrderResponse,
)
from app.auth.jwt import get_current_user
from app.config import Settings, get_settings
from app.core.enums import OrderStatus, TradingMode
from app.core.exceptions import OrderNotFound, PensyError
from app.db.session import get_session
from app.dependencies import TradingState, get_exchange_adapter, get_trading_state, is_live_trading_active
from app.models.order import Order, OrderFill
from app.models.user import User

logger = logging.getLogger("pensy.api.orders")

router = APIRouter(tags=["orders"])


@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="List orders with optional filters",
)
async def list_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by OrderStatus"),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    trading_mode: Optional[str] = Query(None, description="PAPER or LIVE"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    """Return a paginated, filtered list of orders."""
    query = select(Order)

    if status_filter:
        query = query.where(Order.status == status_filter)
    if symbol:
        query = query.where(Order.symbol == symbol.upper())
    if trading_mode:
        query = query.where(Order.trading_mode == trading_mode.upper())

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Fetch page
    query = query.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    orders = result.scalars().all()

    return OrderListResponse(
        orders=[OrderResponse.model_validate(o) for o in orders],
        total=total,
    )


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new order",
)
async def create_order(
    body: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    state: TradingState = Depends(get_trading_state),
) -> OrderResponse:
    """
    Create and submit a new order.

    The order is first persisted in PENDING state, then (in a full
    implementation) forwarded to the OMS pipeline for risk checks and
    exchange submission. This scaffold persists the order and returns it.
    """
    mode = TradingMode.LIVE if is_live_trading_active(settings, state) else TradingMode.PAPER

    order = Order(
        client_order_id=f"pensy-{uuid4().hex[:16]}",
        exchange="paper" if mode == TradingMode.PAPER else "binance_spot",
        symbol=body.symbol.upper(),
        side=body.side.value,
        order_type=body.order_type.value,
        quantity=body.quantity,
        price=body.price,
        time_in_force=body.time_in_force.value,
        status=OrderStatus.PENDING.value,
        trading_mode=mode.value,
        filled_quantity=Decimal("0"),
        strategy_id=body.strategy_id,
    )

    session.add(order)
    await session.flush()
    await session.refresh(order)

    logger.info(
        "Order %s created by %s: %s %s %s qty=%s price=%s mode=%s",
        order.client_order_id,
        current_user.username,
        order.symbol,
        order.side,
        order.order_type,
        order.quantity,
        order.price,
        order.trading_mode,
    )

    # TODO: Forward to OMS service for risk check + exchange submission
    # await oms_service.submit(order)

    return OrderResponse.model_validate(order)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get a single order by ID",
)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Retrieve full details of a single order including fills."""
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFound(str(order_id))

    return OrderResponse.model_validate(order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Request cancellation of an order",
)
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """
    Request cancellation of an active order.

    Sets the order status to CANCEL_PENDING. The actual cancellation on
    the exchange is handled asynchronously by the OMS.
    """
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if order is None:
        raise OrderNotFound(str(order_id))

    order_status = OrderStatus(order.status)
    if order_status.is_terminal:
        raise PensyError(
            f"Cannot cancel order in terminal state: {order.status}",
            code="INVALID_ORDER_STATE",
        )

    order.status = OrderStatus.CANCEL_PENDING.value
    await session.flush()
    await session.refresh(order)

    logger.info(
        "Cancel requested for order %s by %s",
        order.client_order_id,
        current_user.username,
    )

    # TODO: Forward cancel to OMS/exchange adapter
    # await oms_service.cancel(order)

    return OrderResponse.model_validate(order)


@router.get(
    "/fills",
    response_model=list[FillResponse],
    summary="List recent order fills",
)
async def list_fills(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FillResponse]:
    """Return recent fills across all orders, newest first."""
    result = await session.execute(
        select(OrderFill)
        .order_by(OrderFill.fill_time.desc())
        .limit(limit)
        .offset(offset)
    )
    fills = result.scalars().all()
    return [FillResponse.model_validate(f) for f in fills]

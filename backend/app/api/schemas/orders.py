"""
Pydantic request/response schemas for order-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OrderSide, OrderType, OrderStatus, TimeInForce, TradingMode


class OrderCreateRequest(BaseModel):
    """Payload for submitting a new order."""

    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, max_length=32, examples=["BTCUSDT"])
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(..., gt=0, examples=[Decimal("0.01")])
    price: Optional[Decimal] = Field(None, gt=0, description="Required for LIMIT orders")
    time_in_force: TimeInForce = TimeInForce.GTC
    strategy_id: Optional[UUID] = None


class FillResponse(BaseModel):
    """Single order fill."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    quantity: Decimal
    price: Decimal
    commission: Decimal
    fill_time: datetime


class OrderResponse(BaseModel):
    """Full order detail including fills."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_order_id: str
    exchange_order_id: Optional[str] = None
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Optional[Decimal] = None
    status: str
    trading_mode: str
    filled_quantity: Decimal
    avg_fill_price: Optional[Decimal] = None
    reject_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    fills: list[FillResponse] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    orders: list[OrderResponse]
    total: int

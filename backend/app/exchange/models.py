"""
Normalized exchange data models.

These Pydantic models represent the canonical form of data from any exchange.
Exchange adapters map exchange-specific responses into these models.
The OMS, risk engine, and other services only deal with these types.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExchangeOrderResult(BaseModel):
    """Result of placing an order on an exchange."""
    success: bool
    exchange_order_id: str = ""
    client_order_id: str = ""
    status: str = ""  # exchange-reported status
    message: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class ExchangeCancelResult(BaseModel):
    """Result of cancelling an order."""
    success: bool
    exchange_order_id: str = ""
    client_order_id: str = ""
    message: str = ""


class ExchangeOrder(BaseModel):
    """Normalized view of an order on the exchange."""
    exchange_order_id: str
    client_order_id: str = ""
    symbol: str
    side: str  # BUY/SELL
    order_type: str
    quantity: Decimal
    price: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    status: str
    time_in_force: str = "GTC"
    created_at: Optional[datetime] = None


class ExchangePosition(BaseModel):
    """Normalized exchange position."""
    symbol: str
    side: str  # LONG/SHORT/FLAT
    quantity: Decimal
    entry_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    leverage: int = 1


class ExchangeBalance(BaseModel):
    """Normalized exchange balance."""
    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal


class NormalizedTicker(BaseModel):
    """Normalized real-time ticker data."""
    symbol: str
    exchange: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume_24h: Decimal = Decimal("0")
    timestamp: datetime


class UserDataEvent(BaseModel):
    """Normalized user data stream event (fills, order updates)."""
    event_type: str  # ORDER_UPDATE, FILL, BALANCE_UPDATE
    exchange_order_id: str = ""
    client_order_id: str = ""
    symbol: str = ""
    side: str = ""
    status: str = ""
    filled_quantity: Decimal = Decimal("0")
    fill_price: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    commission_asset: str = ""
    timestamp: Optional[datetime] = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ExchangeInfo(BaseModel):
    """Exchange capabilities and metadata."""
    exchange_name: str
    supports_spot: bool = False
    supports_futures: bool = False
    supports_market_orders: bool = True
    supports_limit_orders: bool = True
    supports_stop_orders: bool = False
    supports_post_only: bool = False
    supports_reduce_only: bool = False
    max_orders_per_second: int = 10

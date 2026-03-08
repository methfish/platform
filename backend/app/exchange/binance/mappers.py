"""
Binance-specific response mapping to normalized exchange models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.exchange.models import (
    ExchangeBalance,
    ExchangeOrder,
    ExchangePosition,
    NormalizedTicker,
    UserDataEvent,
)

# Binance order status -> internal status mapping
BINANCE_STATUS_MAP = {
    "NEW": "NEW",
    "PARTIALLY_FILLED": "PARTIALLY_FILLED",
    "FILLED": "FILLED",
    "CANCELED": "CANCELLED",
    "REJECTED": "REJECTED",
    "EXPIRED": "EXPIRED",
    "EXPIRED_IN_MATCH": "EXPIRED",
}


def map_order(raw: dict[str, Any]) -> ExchangeOrder:
    """Map Binance order response to ExchangeOrder."""
    return ExchangeOrder(
        exchange_order_id=str(raw.get("orderId", "")),
        client_order_id=raw.get("clientOrderId", ""),
        symbol=raw.get("symbol", ""),
        side=raw.get("side", ""),
        order_type=raw.get("type", ""),
        quantity=Decimal(str(raw.get("origQty", "0"))),
        price=Decimal(str(raw.get("price", "0"))) or None,
        filled_quantity=Decimal(str(raw.get("executedQty", "0"))),
        avg_fill_price=Decimal(str(raw.get("avgPrice", "0"))) or None,
        status=BINANCE_STATUS_MAP.get(raw.get("status", ""), raw.get("status", "")),
        time_in_force=raw.get("timeInForce", "GTC"),
        created_at=datetime.fromtimestamp(
            raw.get("time", 0) / 1000, tz=timezone.utc
        ) if raw.get("time") else None,
    )


def map_balance(raw: dict[str, Any]) -> ExchangeBalance:
    """Map Binance balance to ExchangeBalance."""
    free = Decimal(str(raw.get("free", "0")))
    locked = Decimal(str(raw.get("locked", "0")))
    return ExchangeBalance(
        asset=raw.get("asset", ""),
        free=free,
        locked=locked,
        total=free + locked,
    )


def map_ticker(raw: dict[str, Any], exchange: str = "binance_spot") -> NormalizedTicker:
    """Map Binance ticker/miniTicker to NormalizedTicker."""
    return NormalizedTicker(
        symbol=raw.get("s", raw.get("symbol", "")),
        exchange=exchange,
        bid=Decimal(str(raw.get("b", raw.get("bidPrice", "0")))),
        ask=Decimal(str(raw.get("a", raw.get("askPrice", "0")))),
        last=Decimal(str(raw.get("c", raw.get("lastPrice", "0")))),
        volume_24h=Decimal(str(raw.get("v", raw.get("volume", "0")))),
        timestamp=datetime.now(timezone.utc),
    )


def map_user_data_event(raw: dict[str, Any]) -> UserDataEvent | None:
    """Map Binance user data stream event to UserDataEvent."""
    event_type = raw.get("e", "")

    if event_type == "executionReport":
        return UserDataEvent(
            event_type="FILL" if raw.get("X") == "FILLED" else "ORDER_UPDATE",
            exchange_order_id=str(raw.get("i", "")),
            client_order_id=raw.get("c", ""),
            symbol=raw.get("s", ""),
            side=raw.get("S", ""),
            status=BINANCE_STATUS_MAP.get(raw.get("X", ""), raw.get("X", "")),
            filled_quantity=Decimal(str(raw.get("l", "0"))),  # Last filled qty
            fill_price=Decimal(str(raw.get("L", "0"))),  # Last filled price
            commission=Decimal(str(raw.get("n", "0"))),
            commission_asset=raw.get("N", ""),
            timestamp=datetime.fromtimestamp(
                raw.get("T", 0) / 1000, tz=timezone.utc
            ) if raw.get("T") else None,
            raw=raw,
        )

    return None

"""
Binance Futures Exchange Adapter - scaffold.

This adapter extends the Binance spot adapter for futures/perpetual contracts.
It uses different API endpoints and supports leverage, positions, and margin.

TODO: Complete implementation when futures trading is needed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import AsyncIterator, Optional

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.base import ExchangeAdapter
from app.exchange.models import (
    ExchangeBalance,
    ExchangeCancelResult,
    ExchangeInfo,
    ExchangeOrder,
    ExchangeOrderResult,
    ExchangePosition,
    NormalizedTicker,
    UserDataEvent,
)

logger = logging.getLogger(__name__)

# Binance Futures API endpoints
BINANCE_FUTURES_URL = "https://fapi.binance.com"
BINANCE_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"


class BinanceFuturesAdapter(ExchangeAdapter):
    """
    Binance USDT-M Futures adapter scaffold.

    This is a placeholder implementation. The adapter interface is complete
    but the actual API calls need Binance Futures-specific implementation.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self._connected = False
        self._testnet = testnet
        logger.warning(
            "BinanceFuturesAdapter is a scaffold. "
            "Complete implementation required before live use."
        )

    async def connect(self) -> None:
        self._connected = True
        logger.info("Binance futures adapter connected (scaffold)")

    async def disconnect(self) -> None:
        self._connected = False

    async def ping(self) -> bool:
        return self._connected

    async def get_exchange_info(self) -> ExchangeInfo:
        return ExchangeInfo(
            exchange_name="binance_futures",
            supports_spot=False,
            supports_futures=True,
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_post_only=True,
            supports_reduce_only=True,
            max_orders_per_second=10,
        )

    async def get_server_time(self) -> int:
        raise NotImplementedError("Futures adapter scaffold")

    async def get_symbols(self) -> list[str]:
        raise NotImplementedError("Futures adapter scaffold")

    async def get_balances(self) -> list[ExchangeBalance]:
        raise NotImplementedError("Futures adapter scaffold")

    async def get_positions(self) -> list[ExchangePosition]:
        raise NotImplementedError("Futures adapter scaffold")

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExchangeOrder]:
        raise NotImplementedError("Futures adapter scaffold")

    async def get_order_status(
        self, symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        raise NotImplementedError("Futures adapter scaffold")

    async def place_order(
        self, symbol: str, side: OrderSide, order_type: OrderType,
        quantity: Decimal, price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        time_in_force: TimeInForce = TimeInForce.GTC, **kwargs,
    ) -> ExchangeOrderResult:
        raise NotImplementedError("Futures adapter scaffold")

    async def cancel_order(
        self, symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeCancelResult:
        raise NotImplementedError("Futures adapter scaffold")

    async def subscribe_ticker(self, symbols: list[str]) -> AsyncIterator[NormalizedTicker]:
        raise NotImplementedError("Futures adapter scaffold")
        yield  # type: ignore

    async def subscribe_user_data(self) -> AsyncIterator[UserDataEvent]:
        raise NotImplementedError("Futures adapter scaffold")
        yield  # type: ignore

    @property
    def exchange_name(self) -> str:
        return "binance_futures"

    @property
    def is_paper(self) -> bool:
        return False

    @property
    def is_connected(self) -> bool:
        return self._connected

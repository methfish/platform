"""
Binance Spot Exchange Adapter.

Implements ExchangeAdapter ABC for Binance spot trading.
This is the live exchange adapter - requires valid API credentials.

NOTE: This adapter requires exchange-specific tuning for production use.
Test thoroughly on Binance testnet before enabling live trading.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import AsyncIterator, Optional

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.base import ExchangeAdapter
from app.exchange.binance.auth import BinanceAuth
from app.exchange.binance.client import BinanceRestClient
from app.exchange.binance.mappers import (
    map_balance,
    map_order,
    map_ticker,
    map_user_data_event,
)
from app.exchange.binance.ws import BinanceWebSocketManager
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


class BinanceSpotAdapter(ExchangeAdapter):
    """
    Live Binance spot adapter.

    WARNING: This adapter places REAL orders on Binance.
    Only use with LIVE_TRADING_ENABLED=true and proper safety controls.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self._auth = BinanceAuth(api_key, api_secret)
        self._client = BinanceRestClient(self._auth, testnet=testnet)
        self._ws_manager = BinanceWebSocketManager(testnet=testnet)
        self._connected = False
        self._testnet = testnet

    async def connect(self) -> None:
        try:
            await self._client.ping()
            self._connected = True
            mode = "TESTNET" if self._testnet else "PRODUCTION"
            logger.info(f"Binance spot adapter connected ({mode})")
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect to Binance: {e}")
            raise

    async def disconnect(self) -> None:
        await self._ws_manager.disconnect()
        await self._client.close()
        self._connected = False

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def get_exchange_info(self) -> ExchangeInfo:
        return ExchangeInfo(
            exchange_name="binance_spot",
            supports_spot=True,
            supports_futures=False,
            supports_market_orders=True,
            supports_limit_orders=True,
            supports_stop_orders=True,
            supports_post_only=False,
            max_orders_per_second=10,
        )

    async def get_server_time(self) -> int:
        return await self._client.get_server_time()

    async def get_symbols(self) -> list[str]:
        info = await self._client.get_exchange_info()
        return [
            s["symbol"]
            for s in info.get("symbols", [])
            if s.get("status") == "TRADING"
        ]

    async def get_balances(self) -> list[ExchangeBalance]:
        account = await self._client.get_account()
        balances = []
        for b in account.get("balances", []):
            balance = map_balance(b)
            if balance.total > 0:
                balances.append(balance)
        return balances

    async def get_positions(self) -> list[ExchangePosition]:
        # Spot doesn't have "positions" - return balances as positions
        balances = await self.get_balances()
        positions = []
        for b in balances:
            if b.asset in ("USDT", "USDC", "BUSD"):
                continue
            if b.total > 0:
                positions.append(ExchangePosition(
                    symbol=f"{b.asset}USDT",
                    side="LONG",
                    quantity=b.total,
                ))
        return positions

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[ExchangeOrder]:
        raw_orders = await self._client.get_open_orders(symbol)
        return [map_order(o) for o in raw_orders]

    async def get_order_status(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeOrder:
        raw = await self._client.get_order(
            symbol,
            order_id=int(exchange_order_id) if exchange_order_id else None,
            client_order_id=client_order_id,
        )
        return map_order(raw)

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        **kwargs,
    ) -> ExchangeOrderResult:
        try:
            raw = await self._client.place_order(
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                price=price,
                client_order_id=client_order_id,
                time_in_force=time_in_force.value,
            )
            return ExchangeOrderResult(
                success=True,
                exchange_order_id=str(raw.get("orderId", "")),
                client_order_id=raw.get("clientOrderId", client_order_id or ""),
                status=raw.get("status", ""),
                raw=raw,
            )
        except Exception as e:
            logger.error(f"Binance place_order failed: {e}")
            return ExchangeOrderResult(
                success=False,
                client_order_id=client_order_id or "",
                message=str(e),
            )

    async def cancel_order(
        self,
        symbol: str,
        exchange_order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> ExchangeCancelResult:
        try:
            raw = await self._client.cancel_order(
                symbol=symbol,
                order_id=int(exchange_order_id) if exchange_order_id else None,
                client_order_id=client_order_id,
            )
            return ExchangeCancelResult(
                success=True,
                exchange_order_id=str(raw.get("orderId", "")),
                client_order_id=raw.get("origClientOrderId", ""),
            )
        except Exception as e:
            return ExchangeCancelResult(
                success=False,
                message=str(e),
            )

    async def subscribe_ticker(self, symbols: list[str]) -> AsyncIterator[NormalizedTicker]:
        async for raw in self._ws_manager.connect_ticker_stream(symbols):
            ticker = map_ticker(raw, exchange="binance_spot")
            yield ticker

    async def subscribe_user_data(self) -> AsyncIterator[UserDataEvent]:
        # TODO: Implement listen key creation/renewal via REST API
        # For now, this is a scaffold
        listen_key = "placeholder"
        async for raw in self._ws_manager.connect_user_data_stream(listen_key):
            event = map_user_data_event(raw)
            if event:
                yield event

    @property
    def exchange_name(self) -> str:
        return "binance_spot"

    @property
    def is_paper(self) -> bool:
        return False

    @property
    def is_connected(self) -> bool:
        return self._connected

"""
Binance REST API client.

Handles HTTP communication with Binance spot API.
Uses aiohttp for async requests with timeout and retry logic.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

import aiohttp

from app.exchange.binance.auth import BinanceAuth
from app.exchange.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Binance API endpoints
BINANCE_SPOT_URL = "https://api.binance.com"
BINANCE_SPOT_TESTNET_URL = "https://testnet.binance.vision"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class BinanceRestClient:
    """
    Async REST client for Binance spot API.

    All requests go through rate limiting and authentication.
    Responses are returned as raw dicts; mapping happens in the adapter.
    """

    def __init__(
        self,
        auth: BinanceAuth,
        testnet: bool = True,
        rate_limiter: RateLimiter | None = None,
    ):
        self._auth = auth
        self._base_url = BINANCE_SPOT_TESTNET_URL if testnet else BINANCE_SPOT_URL
        self._rate_limiter = rate_limiter or RateLimiter(max_requests=10, window_seconds=1.0)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=DEFAULT_TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        """Execute an API request with rate limiting and error handling."""
        await self._rate_limiter.acquire()

        url = f"{self._base_url}{path}"
        params = params or {}

        if signed:
            params = self._auth.sign(params)

        headers = self._auth.headers()
        session = await self._get_session()

        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            elif method == "POST":
                async with session.post(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientError as e:
            logger.error(f"Binance API request failed: {e}")
            raise

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> dict[str, Any]:
        """Process API response, raise on errors."""
        data = await resp.json()
        if resp.status != 200:
            error_code = data.get("code", resp.status)
            error_msg = data.get("msg", "Unknown error")
            logger.error(f"Binance API error: {error_code} - {error_msg}")
            raise BinanceAPIError(error_code, error_msg)
        return data

    # --- Public endpoints ---

    async def ping(self) -> bool:
        await self._request("GET", "/api/v3/ping")
        return True

    async def get_server_time(self) -> int:
        data = await self._request("GET", "/api/v3/time")
        return data["serverTime"]

    async def get_exchange_info(self) -> dict:
        return await self._request("GET", "/api/v3/exchangeInfo")

    async def get_ticker(self, symbol: str) -> dict:
        return await self._request("GET", "/api/v3/ticker/24hr", {"symbol": symbol})

    # --- Account endpoints (signed) ---

    async def get_account(self) -> dict:
        return await self._request("GET", "/api/v3/account", signed=True)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = await self._request("GET", "/api/v3/openOrders", params, signed=True)
        return data if isinstance(data, list) else []

    async def get_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._request("GET", "/api/v3/order", params, signed=True)

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "GTC",
    ) -> dict:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }
        if price:
            params["price"] = str(price)
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        if order_type == "LIMIT":
            params["timeInForce"] = time_in_force
        params["newOrderRespType"] = "FULL"

        return await self._request("POST", "/api/v3/order", params, signed=True)

    async def cancel_order(
        self,
        symbol: str,
        order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._request("DELETE", "/api/v3/order", params, signed=True)

    # --- Raw-response endpoints (list or dict) ---

    async def _request_raw(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        signed: bool = False,
    ) -> Any:
        """Execute an API request returning raw JSON (list or dict).

        Unlike ``_request`` which assumes a dict response, this method
        handles Binance endpoints that return JSON arrays (e.g.
        ``/api/v3/ticker/24hr`` without a symbol, ``/api/v3/klines``).
        """
        await self._rate_limiter.acquire()
        url = f"{self._base_url}{path}"
        params = params or {}
        if signed:
            params = self._auth.sign(params)
        headers = self._auth.headers()
        session = await self._get_session()
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if resp.status != 200:
                    error_code = (
                        data.get("code", resp.status)
                        if isinstance(data, dict)
                        else resp.status
                    )
                    error_msg = (
                        data.get("msg", "Unknown error")
                        if isinstance(data, dict)
                        else str(data)
                    )
                    logger.error(f"Binance API error: {error_code} - {error_msg}")
                    raise BinanceAPIError(error_code, error_msg)
                return data
        except aiohttp.ClientError as e:
            logger.error(f"Binance API request failed: {e}")
            raise

    async def get_all_tickers(self) -> list[dict]:
        """Get 24hr ticker data for all symbols."""
        return await self._request_raw("GET", "/api/v3/ticker/24hr")

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list[list]:
        """Get kline/candlestick bars for a symbol.

        Returns list of lists: ``[open_time, open, high, low, close,
        volume, close_time, quote_volume, trades, taker_buy_base,
        taker_buy_quote, ignore]``
        """
        return await self._request_raw(
            "GET",
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )


class BinanceAPIError(Exception):
    """Binance API returned an error."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error [{code}]: {message}")

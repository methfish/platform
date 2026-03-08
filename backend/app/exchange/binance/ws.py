"""
Binance WebSocket manager for real-time market data and user data streams.

Handles connection lifecycle, auto-reconnection, and message parsing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable

import websockets

logger = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_WS_TESTNET_URL = "wss://testnet.binance.vision/ws"

RECONNECT_DELAY_INITIAL = 1.0
RECONNECT_DELAY_MAX = 60.0


class BinanceWebSocketManager:
    """
    Manages Binance WebSocket connections with auto-reconnect.

    Supports:
    - Individual symbol streams (e.g., btcusdt@ticker)
    - Combined streams (multiple symbols in one connection)
    - User data streams (requires listen key)
    """

    def __init__(self, testnet: bool = True):
        self._base_url = BINANCE_WS_TESTNET_URL if testnet else BINANCE_WS_URL
        self._ws = None
        self._running = False
        self._reconnect_delay = RECONNECT_DELAY_INITIAL

    async def connect_ticker_stream(
        self,
        symbols: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Connect to ticker streams for multiple symbols.

        Yields raw ticker messages. Handles reconnection automatically.
        """
        streams = "/".join(f"{s.lower()}@miniTicker" for s in symbols)
        url = f"{self._base_url}/{streams}"

        self._running = True
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._ws = ws
                    self._reconnect_delay = RECONNECT_DELAY_INITIAL
                    logger.info(f"WebSocket connected: {len(symbols)} ticker streams")

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            yield data
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid WebSocket message: {message[:100]}")

            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, RECONNECT_DELAY_MAX
                )

    async def connect_user_data_stream(
        self,
        listen_key: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Connect to user data stream for real-time order/fill updates.

        The listen_key must be obtained via REST API and renewed every 30 minutes.
        """
        url = f"{self._base_url}/{listen_key}"

        self._running = True
        while self._running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    self._ws = ws
                    logger.info("User data WebSocket connected")

                    async for message in ws:
                        try:
                            data = json.loads(message)
                            yield data
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid user data message: {message[:100]}")

            except websockets.ConnectionClosed:
                logger.warning("User data WebSocket closed")
            except Exception as e:
                logger.error(f"User data WebSocket error: {e}")

            if self._running:
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, RECONNECT_DELAY_MAX
                )

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None

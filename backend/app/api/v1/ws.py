"""
WebSocket endpoint for real-time streaming of order updates and market data.

Clients connect to /ws and receive JSON messages for order lifecycle events
and ticker price updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("pensy.api.ws")

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Simple WebSocket connection manager.

    Tracks active connections and provides broadcast/unicast helpers.
    Thread-safety note: this is designed for a single-process asyncio server.
    For multi-process deployments, use Redis pub/sub as the fanout layer.
    """

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("WebSocket client connected (total=%d)", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        self._active.remove(ws)
        logger.info("WebSocket client disconnected (total=%d)", len(self._active))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients."""
        payload = json.dumps(message)
        stale: list[WebSocket] = []
        for ws in self._active:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._active.remove(ws)

    async def send_personal(self, ws: WebSocket, message: dict[str, Any]) -> None:
        """Send a JSON message to a single client."""
        await ws.send_text(json.dumps(message))

    @property
    def active_count(self) -> int:
        return len(self._active)


# Singleton manager - imported by other modules to broadcast events
ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    WebSocket endpoint that streams real-time updates to connected clients.

    After connection, the server sends periodic heartbeats and relays any
    order update or market data events that are broadcast through the
    ``ws_manager``.

    Clients can send JSON messages to subscribe to specific channels::

        {"action": "subscribe", "channel": "orders"}
        {"action": "subscribe", "channel": "tickers"}
        {"action": "ping"}

    The server responds with matching events or a pong.
    """
    await ws_manager.connect(ws)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat on idle
                await ws_manager.send_personal(ws, {"type": "heartbeat"})
                continue

            # Parse client message
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_personal(
                    ws, {"type": "error", "message": "Invalid JSON"}
                )
                continue

            action = msg.get("action", "")

            if action == "ping":
                await ws_manager.send_personal(ws, {"type": "pong"})
            elif action == "subscribe":
                channel = msg.get("channel", "")
                await ws_manager.send_personal(
                    ws,
                    {
                        "type": "subscribed",
                        "channel": channel,
                        "message": f"Subscribed to {channel}",
                    },
                )
            else:
                await ws_manager.send_personal(
                    ws,
                    {"type": "error", "message": f"Unknown action: {action}"},
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        logger.exception("WebSocket error")
        ws_manager.disconnect(ws)

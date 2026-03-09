"""
Top-level API router that aggregates all v1 route modules.

Mounts all endpoint groups under /api/v1 with appropriate prefixes and
includes the WebSocket endpoint at /ws.

Usage in main.py::

    from app.api.router import api_router
    app.include_router(api_router)
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    agents,
    auth,
    market_data,
    markets,
    orders,
    positions,
    reconciliation,
    research,
    risk,
    strategies,
    strategy_engine,
    ws,
)

api_router = APIRouter()

# --- v1 REST endpoints ---

api_router.include_router(
    auth.router,
    prefix="/api/v1",
)

api_router.include_router(
    orders.router,
    prefix="/api/v1",
)

api_router.include_router(
    positions.router,
    prefix="/api/v1",
)

api_router.include_router(
    strategies.router,
    prefix="/api/v1",
)

api_router.include_router(
    risk.router,
    prefix="/api/v1",
)

api_router.include_router(
    admin.router,
    prefix="/api/v1",
)

api_router.include_router(
    reconciliation.router,
    prefix="/api/v1",
)

api_router.include_router(
    market_data.router,
    prefix="/api/v1",
)

api_router.include_router(
    markets.router,
    prefix="/api/v1",
)

api_router.include_router(
    agents.router,
    prefix="/api/v1",
)

api_router.include_router(
    strategy_engine.router,
    prefix="/api/v1",
)

api_router.include_router(
    research.router,
    prefix="/api/v1",
)

# --- WebSocket (no /api/v1 prefix) ---

api_router.include_router(ws.router)

"""
Market data endpoints.

GET /market-data/tickers - Current ticker prices from the exchange adapter
                           or cached values.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import Settings, get_settings
from app.db.session import get_session
from app.models.market_data import TickerSnapshot
from app.models.user import User

logger = logging.getLogger("pensy.api.market_data")

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.get(
    "/tickers",
    summary="Get current ticker prices",
)
async def get_tickers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Return the latest ticker snapshot for each configured symbol.

    In a full implementation this would first check a Redis cache populated
    by the market data websocket subscription, falling back to the most
    recent DB snapshots.
    """
    symbols = settings.market_data_symbols_list

    tickers: list[dict[str, Any]] = []

    for symbol in symbols:
        result = await session.execute(
            select(TickerSnapshot)
            .where(TickerSnapshot.symbol == symbol)
            .order_by(TickerSnapshot.snapshot_time.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot is not None:
            tickers.append(
                {
                    "symbol": snapshot.symbol,
                    "exchange": snapshot.exchange,
                    "bid": str(snapshot.bid),
                    "ask": str(snapshot.ask),
                    "last": str(snapshot.last),
                    "volume_24h": str(snapshot.volume_24h),
                    "snapshot_time": snapshot.snapshot_time.isoformat(),
                }
            )
        else:
            tickers.append(
                {
                    "symbol": symbol,
                    "exchange": "unknown",
                    "bid": "0",
                    "ask": "0",
                    "last": "0",
                    "volume_24h": "0",
                    "snapshot_time": None,
                }
            )

    return {"tickers": tickers, "count": len(tickers)}

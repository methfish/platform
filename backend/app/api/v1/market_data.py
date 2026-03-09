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
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import Settings, get_settings
from app.db.session import get_session
from app.models.market_data import TickerSnapshot
from app.models.user import User

logger = logging.getLogger("pensy.api.market_data")

router = APIRouter(prefix="/market-data", tags=["market-data"])

# Exchange -> asset class mapping
_EXCHANGE_ASSET_CLASS = {
    "forex_sim": "forex",
    "alpaca": "stock",
    "binance_spot": "crypto",
    "binance_futures": "crypto",
    "paper": "crypto",
    "unknown": "crypto",
}


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
    Return the latest ticker snapshot for every symbol in the DB,
    including simulated forex and stock tickers.
    """
    # Get the most recent snapshot per symbol using a subquery
    subq = (
        select(
            TickerSnapshot.symbol,
            func.max(TickerSnapshot.snapshot_time).label("max_time"),
        )
        .group_by(TickerSnapshot.symbol)
        .subquery()
    )

    result = await session.execute(
        select(TickerSnapshot).join(
            subq,
            (TickerSnapshot.symbol == subq.c.symbol)
            & (TickerSnapshot.snapshot_time == subq.c.max_time),
        )
    )
    snapshots = result.scalars().all()

    # Also include configured crypto symbols that have no snapshot yet
    snapshot_symbols = {s.symbol for s in snapshots}
    tickers: list[dict[str, Any]] = []

    for snapshot in snapshots:
        asset_class = _EXCHANGE_ASSET_CLASS.get(snapshot.exchange, "crypto")
        tickers.append({
            "symbol": snapshot.symbol,
            "exchange": snapshot.exchange,
            "asset_class": asset_class,
            "bid": str(snapshot.bid),
            "ask": str(snapshot.ask),
            "last": str(snapshot.last),
            "volume_24h": str(snapshot.volume_24h),
            "snapshot_time": snapshot.snapshot_time.isoformat(),
            "change_percent_24h": 0.0,
        })

    # Add placeholder rows for configured crypto symbols not yet in DB
    for symbol in settings.market_data_symbols_list:
        if symbol not in snapshot_symbols:
            tickers.append({
                "symbol": symbol,
                "exchange": "unknown",
                "asset_class": "crypto",
                "bid": "0",
                "ask": "0",
                "last": "0",
                "volume_24h": "0",
                "snapshot_time": None,
                "change_percent_24h": 0.0,
            })

    # Sort: forex first, then stocks, then crypto
    order = {"forex": 0, "stock": 1, "crypto": 2}
    tickers.sort(key=lambda t: (order.get(t["asset_class"], 9), t["symbol"]))

    return {"tickers": tickers, "count": len(tickers)}

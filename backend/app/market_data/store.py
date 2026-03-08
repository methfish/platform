"""
Market data store - Redis cache for latest tickers with staleness tracking.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.exchange.models import NormalizedTicker

logger = logging.getLogger(__name__)

# In-memory fallback when Redis is not available
_memory_store: dict[str, dict] = {}


class MarketDataStore:
    """
    Stores latest market data in Redis (or in-memory fallback).

    Each ticker is stored as a JSON hash with a TTL.
    Staleness is determined by comparing the stored timestamp with now.
    """

    def __init__(self, redis_client=None, ttl_seconds: int = 60):
        self._redis = redis_client
        self._ttl = ttl_seconds

    async def update_ticker(self, ticker: NormalizedTicker) -> None:
        """Store latest ticker data."""
        key = f"ticker:{ticker.symbol}"
        data = {
            "symbol": ticker.symbol,
            "exchange": ticker.exchange,
            "bid": str(ticker.bid),
            "ask": str(ticker.ask),
            "last": str(ticker.last),
            "volume_24h": str(ticker.volume_24h),
            "timestamp": ticker.timestamp.isoformat(),
        }

        if self._redis:
            try:
                await self._redis.set(key, json.dumps(data), ex=self._ttl)
            except Exception as e:
                logger.warning(f"Redis write failed, using memory: {e}")
                _memory_store[key] = data
        else:
            _memory_store[key] = data

    async def get_ticker(self, symbol: str) -> NormalizedTicker | None:
        """Get latest ticker for a symbol."""
        key = f"ticker:{symbol}"
        data = None

        if self._redis:
            try:
                raw = await self._redis.get(key)
                if raw:
                    data = json.loads(raw)
            except Exception:
                data = _memory_store.get(key)
        else:
            data = _memory_store.get(key)

        if not data:
            return None

        return NormalizedTicker(
            symbol=data["symbol"],
            exchange=data["exchange"],
            bid=Decimal(data["bid"]),
            ask=Decimal(data["ask"]),
            last=Decimal(data["last"]),
            volume_24h=Decimal(data["volume_24h"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )

    async def get_all_tickers(self) -> list[NormalizedTicker]:
        """Get all stored tickers."""
        tickers = []
        if self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(match="ticker:*"):
                    keys.append(key)
                for key in keys:
                    raw = await self._redis.get(key)
                    if raw:
                        data = json.loads(raw)
                        tickers.append(NormalizedTicker(
                            symbol=data["symbol"],
                            exchange=data["exchange"],
                            bid=Decimal(data["bid"]),
                            ask=Decimal(data["ask"]),
                            last=Decimal(data["last"]),
                            volume_24h=Decimal(data["volume_24h"]),
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                        ))
            except Exception as e:
                logger.warning(f"Redis scan failed: {e}")
        else:
            for data in _memory_store.values():
                tickers.append(NormalizedTicker(
                    symbol=data["symbol"],
                    exchange=data["exchange"],
                    bid=Decimal(data["bid"]),
                    ask=Decimal(data["ask"]),
                    last=Decimal(data["last"]),
                    volume_24h=Decimal(data["volume_24h"]),
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                ))
        return tickers

    def is_stale(self, ticker: NormalizedTicker, max_age_seconds: int = 30) -> bool:
        """Check if a ticker is stale (older than max_age_seconds)."""
        age = (datetime.now(timezone.utc) - ticker.timestamp).total_seconds()
        return age > max_age_seconds

    async def get_last_price(self, symbol: str) -> Decimal | None:
        """Get just the last price for a symbol."""
        ticker = await self.get_ticker(symbol)
        return ticker.last if ticker else None

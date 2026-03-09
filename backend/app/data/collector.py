"""
Historical market data collector using CCXT.

Fetches OHLCV candles, recent trades, and order book snapshots from
crypto exchanges and persists them to PostgreSQL via the OHLCVBar model.

Designed for a small research operation:
  - Start with 1m and 5m candles for a few symbols
  - Backfill history incrementally (exchange rate-limit safe)
  - Resume from the last stored bar to avoid duplicates
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import OHLCVBar

logger = logging.getLogger("pensy.data.collector")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")

DEFAULT_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
]

DEFAULT_INTERVALS = ["1m", "5m"]


@dataclass
class CollectionJob:
    """Describes a single data collection task."""

    exchange_id: str = "binance"
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    intervals: list[str] = field(default_factory=lambda: list(DEFAULT_INTERVALS))
    since: Optional[datetime] = None  # If None, backfill from exchange default
    limit: int = 500  # Candles per request


@dataclass
class CollectionStatus:
    """Real-time status of a collection run."""

    job_id: str = ""
    exchange: str = ""
    status: str = "idle"  # idle | running | completed | error
    symbols_total: int = 0
    symbols_done: int = 0
    bars_inserted: int = 0
    bars_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_symbol: str = ""
    current_interval: str = ""

    @property
    def progress_pct(self) -> float:
        if self.symbols_total == 0:
            return 0.0
        return round(self.symbols_done / self.symbols_total * 100, 1)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class MarketDataCollector:
    """
    Async CCXT-based collector for historical OHLCV data.

    Usage:
        collector = MarketDataCollector()
        await collector.initialize("binance")
        status = await collector.collect(job, session)
        await collector.close()
    """

    def __init__(self) -> None:
        self._exchange: Any = None
        self._exchange_id: str = ""
        self._status = CollectionStatus()

    @property
    def status(self) -> CollectionStatus:
        return self._status

    async def initialize(self, exchange_id: str = "binance") -> None:
        """Create the CCXT async exchange instance."""
        try:
            import ccxt.async_support as ccxt
        except ImportError:
            raise ImportError(
                "ccxt is required for data collection. "
                "Install with: pip install ccxt"
            )

        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unknown exchange: {exchange_id}")

        self._exchange = exchange_class({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        self._exchange_id = exchange_id
        await self._exchange.load_markets()
        logger.info("Initialized CCXT exchange: %s (%d markets)",
                     exchange_id, len(self._exchange.markets))

    async def close(self) -> None:
        """Close the exchange connection."""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None

    async def collect(
        self,
        job: CollectionJob,
        session: AsyncSession,
    ) -> CollectionStatus:
        """
        Run a data collection job.

        Fetches OHLCV candles for each symbol/interval pair and upserts
        them into the ohlcv_bars table.
        """
        if self._exchange is None:
            await self.initialize(job.exchange_id)

        self._status = CollectionStatus(
            job_id=f"{job.exchange_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            exchange=job.exchange_id,
            status="running",
            symbols_total=len(job.symbols) * len(job.intervals),
            started_at=datetime.now(timezone.utc),
        )

        for symbol in job.symbols:
            for interval in job.intervals:
                self._status.current_symbol = symbol
                self._status.current_interval = interval
                try:
                    inserted, skipped = await self._fetch_and_store(
                        symbol, interval, job.since, job.limit, session
                    )
                    self._status.bars_inserted += inserted
                    self._status.bars_skipped += skipped
                except Exception as exc:
                    error_msg = f"{symbol}/{interval}: {exc}"
                    logger.error("Collection error: %s", error_msg)
                    self._status.errors.append(error_msg)

                self._status.symbols_done += 1

        self._status.status = "completed" if not self._status.errors else "completed_with_errors"
        self._status.completed_at = datetime.now(timezone.utc)
        self._status.current_symbol = ""
        self._status.current_interval = ""

        logger.info(
            "Collection complete: %d inserted, %d skipped, %d errors",
            self._status.bars_inserted,
            self._status.bars_skipped,
            len(self._status.errors),
        )
        return self._status

    async def _fetch_and_store(
        self,
        symbol: str,
        interval: str,
        since: Optional[datetime],
        limit: int,
        session: AsyncSession,
    ) -> tuple[int, int]:
        """Fetch OHLCV from exchange and upsert into DB. Returns (inserted, skipped)."""
        # Determine start timestamp
        since_ms: Optional[int] = None
        if since:
            since_ms = int(since.timestamp() * 1000)
        else:
            # Resume from last stored bar
            last_time = await self._get_last_bar_time(symbol, interval, session)
            if last_time:
                since_ms = int(last_time.timestamp() * 1000) + 1

        # Normalize symbol for CCXT (BTC/USDT)
        ccxt_symbol = symbol if "/" in symbol else symbol.replace("USDT", "/USDT")

        candles = await self._exchange.fetch_ohlcv(
            ccxt_symbol, interval, since=since_ms, limit=limit
        )

        if not candles:
            return 0, 0

        # Normalize symbol for storage (BTCUSDT)
        db_symbol = symbol.replace("/", "")

        inserted = 0
        skipped = 0

        # Batch upsert using PostgreSQL ON CONFLICT
        rows = []
        for candle in candles:
            ts, o, h, l, c, v = candle
            open_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

            # Estimate close time based on interval
            close_time = self._estimate_close_time(open_time, interval)

            rows.append({
                "symbol": db_symbol,
                "interval": interval,
                "open_time": open_time,
                "open": Decimal(str(o)),
                "high": Decimal(str(h)),
                "low": Decimal(str(l)),
                "close": Decimal(str(c)),
                "volume": Decimal(str(v)),
                "close_time": close_time,
                "quote_volume": Decimal("0"),
                "trades": 0,
            })

        if rows:
            stmt = pg_insert(OHLCVBar).values(rows)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["symbol", "interval", "open_time"]
            )
            result = await session.execute(stmt)
            await session.commit()
            inserted = result.rowcount if result.rowcount else len(rows)
            skipped = len(rows) - inserted

        logger.info(
            "Fetched %s %s: %d candles (%d new, %d existing)",
            db_symbol, interval, len(candles), inserted, skipped,
        )
        return inserted, skipped

    async def _get_last_bar_time(
        self, symbol: str, interval: str, session: AsyncSession
    ) -> Optional[datetime]:
        """Get the most recent bar timestamp for a symbol/interval pair."""
        db_symbol = symbol.replace("/", "")
        result = await session.execute(
            select(func.max(OHLCVBar.open_time)).where(
                OHLCVBar.symbol == db_symbol,
                OHLCVBar.interval == interval,
            )
        )
        return result.scalar_one_or_none()

    def _estimate_close_time(self, open_time: datetime, interval: str) -> datetime:
        """Estimate bar close time from interval string."""
        from datetime import timedelta

        multipliers = {
            "1m": timedelta(minutes=1),
            "3m": timedelta(minutes=3),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "2h": timedelta(hours=2),
            "4h": timedelta(hours=4),
            "6h": timedelta(hours=6),
            "8h": timedelta(hours=8),
            "12h": timedelta(hours=12),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
        }
        delta = multipliers.get(interval, timedelta(minutes=1))
        return open_time + delta - timedelta(milliseconds=1)

    async def get_data_summary(self, session: AsyncSession) -> dict:
        """Return summary stats about stored data."""
        result = await session.execute(
            select(
                OHLCVBar.symbol,
                OHLCVBar.interval,
                func.count(OHLCVBar.id).label("bar_count"),
                func.min(OHLCVBar.open_time).label("earliest"),
                func.max(OHLCVBar.open_time).label("latest"),
            ).group_by(OHLCVBar.symbol, OHLCVBar.interval)
        )
        rows = result.all()
        return {
            "datasets": [
                {
                    "symbol": r.symbol,
                    "interval": r.interval,
                    "bar_count": r.bar_count,
                    "earliest": r.earliest.isoformat() if r.earliest else None,
                    "latest": r.latest.isoformat() if r.latest else None,
                }
                for r in rows
            ],
            "total_bars": sum(r.bar_count for r in rows),
        }

"""
Historical market data collector.

Delegates to YFinanceCollector for fetching OHLCV candles from
Yahoo Finance (forex pairs and stocks) and persists them to
PostgreSQL via the OHLCVBar model.

Default symbols cover major forex pairs and popular US equities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("pensy.data.collector")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "1d")

DEFAULT_SYMBOLS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AAPL",
    "MSFT",
    "SPY",
]

DEFAULT_INTERVALS = ["1h", "1d"]


@dataclass
class CollectionJob:
    """Describes a single data collection task."""

    exchange_id: str = "yfinance"
    symbols: list[str] = field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    intervals: list[str] = field(default_factory=lambda: list(DEFAULT_INTERVALS))
    since: Optional[datetime] = None  # If None, backfill from default period
    limit: int = 500  # Kept for API compat (not used by yfinance)


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
# Collector (delegates to YFinanceCollector)
# ---------------------------------------------------------------------------

class MarketDataCollector:
    """
    Market data collector that delegates to YFinanceCollector.

    Usage:
        collector = MarketDataCollector()
        await collector.initialize()
        status = await collector.collect(job, session)
        await collector.close()
    """

    def __init__(self) -> None:
        self._yf_collector: Any = None
        self._status = CollectionStatus()

    @property
    def status(self) -> CollectionStatus:
        return self._status

    async def initialize(self, exchange_id: str = "yfinance") -> None:
        """Create the YFinanceCollector instance."""
        from app.data.yfinance_collector import YFinanceCollector

        self._yf_collector = YFinanceCollector()
        logger.info("Initialized YFinance collector")

    async def close(self) -> None:
        """No-op -- yfinance does not require cleanup."""
        pass

    async def collect(
        self,
        job: CollectionJob,
        session: AsyncSession,
    ) -> CollectionStatus:
        """
        Run a data collection job via YFinanceCollector.

        Fetches OHLCV candles for each symbol/interval pair and upserts
        them into the ohlcv_bars table.
        """
        if self._yf_collector is None:
            await self.initialize(job.exchange_id)

        self._status = await self._yf_collector.collect(job, session)
        return self._status

    async def get_data_summary(self, session: AsyncSession) -> dict:
        """Return summary stats about stored data."""
        if self._yf_collector is None:
            await self.initialize()

        return await self._yf_collector.get_data_summary(session)

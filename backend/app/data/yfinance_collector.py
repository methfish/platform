"""
Historical market data collector using yfinance.

Fetches OHLCV candles for forex pairs and stocks from Yahoo Finance
and persists them to PostgreSQL via the OHLCVBar model.

Forex symbol mapping:
  - EURUSD -> EURUSD=X
  - USDJPY -> JPY=X  (inverted pairs use the counter-currency)
  - Stocks pass through directly (AAPL, MSFT, SPY, etc.)

yfinance period limits per interval:
  - 1m:  7 days
  - 5m:  60 days
  - 15m: 60 days
  - 1h:  730 days
  - 1d:  max
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.collector import CollectionJob, CollectionStatus
from app.models.market_data import OHLCVBar

logger = logging.getLogger("pensy.data.yfinance_collector")

# ---------------------------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------------------------

FOREX_SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
    "NZDUSD": "NZDUSD=X",
    "EURGBP": "EURGBP=X",
}

# yfinance interval -> max lookback period string
INTERVAL_PERIOD_LIMITS: dict[str, str] = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "1h": "730d",
    "1d": "max",
}

# Interval -> timedelta for close_time estimation
INTERVAL_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def _map_symbol(symbol: str) -> str:
    """Map a platform symbol to a yfinance ticker."""
    return FOREX_SYMBOL_MAP.get(symbol, symbol)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class YFinanceCollector:
    """
    Collects OHLCV data from Yahoo Finance for forex and stock symbols.

    yfinance is synchronous, so all download calls are wrapped with
    ``asyncio.to_thread()`` to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        try:
            import yfinance  # noqa: F401
        except ImportError:
            raise ImportError(
                "yfinance is required for data collection. "
                "Install with: pip install yfinance"
            )

    # ---- public API --------------------------------------------------------

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
        status = CollectionStatus(
            job_id=f"yfinance_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            exchange="yfinance",
            status="running",
            symbols_total=len(job.symbols) * len(job.intervals),
            started_at=datetime.now(timezone.utc),
        )

        for symbol in job.symbols:
            for interval in job.intervals:
                status.current_symbol = symbol
                status.current_interval = interval
                try:
                    inserted, skipped = await self._fetch_and_store(
                        symbol, interval, job.since, session,
                    )
                    status.bars_inserted += inserted
                    status.bars_skipped += skipped
                except Exception as exc:
                    error_msg = f"{symbol}/{interval}: {exc}"
                    logger.error("Collection error: %s", error_msg)
                    status.errors.append(error_msg)

                status.symbols_done += 1

        status.status = "completed" if not status.errors else "completed_with_errors"
        status.completed_at = datetime.now(timezone.utc)
        status.current_symbol = ""
        status.current_interval = ""

        logger.info(
            "Collection complete: %d inserted, %d skipped, %d errors",
            status.bars_inserted,
            status.bars_skipped,
            len(status.errors),
        )
        return status

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

    # ---- internals ---------------------------------------------------------

    async def _fetch_and_store(
        self,
        symbol: str,
        interval: str,
        since: Optional[datetime],
        session: AsyncSession,
    ) -> tuple[int, int]:
        """Fetch OHLCV from yfinance and upsert into DB. Returns (inserted, skipped)."""
        import yfinance as yf

        yf_ticker = _map_symbol(symbol)
        period = INTERVAL_PERIOD_LIMITS.get(interval, "max")

        # If a start date is given, use start/end instead of period
        start_str: Optional[str] = None
        end_str: Optional[str] = None
        use_period = True

        if since:
            start_str = since.strftime("%Y-%m-%d")
            end_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            use_period = False
        else:
            # Try to resume from last stored bar
            last_time = await self._get_last_bar_time(symbol, interval, session)
            if last_time:
                start_str = (last_time + timedelta(seconds=1)).strftime("%Y-%m-%d")
                end_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                use_period = False

        # yfinance.download is synchronous -- run in a thread
        if use_period:
            df = await asyncio.to_thread(
                yf.download,
                tickers=yf_ticker,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )
        else:
            df = await asyncio.to_thread(
                yf.download,
                tickers=yf_ticker,
                start=start_str,
                end=end_str,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )

        if df is None or df.empty:
            return 0, 0

        # Handle multi-level columns from yf.download (single ticker)
        if hasattr(df.columns, "levels") and len(df.columns.levels) > 1:
            df.columns = df.columns.droplevel("Ticker")

        interval_delta = INTERVAL_DELTAS.get(interval, timedelta(minutes=1))

        rows = []
        for ts, row in df.iterrows():
            # ts is a pandas Timestamp; convert to datetime
            open_time = ts.to_pydatetime()
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)

            close_time = open_time + interval_delta - timedelta(milliseconds=1)

            rows.append({
                "symbol": symbol,
                "interval": interval,
                "open_time": open_time,
                "open": Decimal(str(round(float(row["Open"]), 8))),
                "high": Decimal(str(round(float(row["High"]), 8))),
                "low": Decimal(str(round(float(row["Low"]), 8))),
                "close": Decimal(str(round(float(row["Close"]), 8))),
                "volume": Decimal(str(round(float(row.get("Volume", 0)), 8))),
                "close_time": close_time,
                "quote_volume": Decimal("0"),
                "trades": 0,
            })

        if not rows:
            return 0, 0

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
            symbol, interval, len(rows), inserted, skipped,
        )
        return inserted, skipped

    async def _get_last_bar_time(
        self, symbol: str, interval: str, session: AsyncSession,
    ) -> Optional[datetime]:
        """Get the most recent bar timestamp for a symbol/interval pair."""
        result = await session.execute(
            select(func.max(OHLCVBar.open_time)).where(
                OHLCVBar.symbol == symbol,
                OHLCVBar.interval == interval,
            )
        )
        return result.scalar_one_or_none()

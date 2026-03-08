"""Market data scraper - continuously fetches and persists market data."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exchange.binance.client import BinanceRestClient
from app.market_data.normalizer import normalize_ticker_from_raw
from app.market_data.store import MarketDataStore
from app.models.market_data import OHLCVBar

logger = logging.getLogger(__name__)


class MarketScraper:
    """Scrapes market data from Binance and persists to Redis and DB."""

    def __init__(
        self,
        binance_client: BinanceRestClient,
        store: MarketDataStore,
        session_factory,
        settings: Settings,
    ):
        self._client = binance_client
        self._store = store
        self._session_factory = session_factory
        self._settings = settings
        self._running = False
        self._task: asyncio.Task | None = None

    async def scrape_tickers(self) -> int:
        """Fetch all 24hr tickers and store in Redis.

        Returns number of tickers scraped.
        """
        try:
            tickers_raw = await self._client.get_all_tickers()
            count = 0
            for ticker_dict in tickers_raw:
                symbol = ticker_dict.get("symbol", "").upper()
                if not symbol:
                    continue

                # Check if we should scrape this symbol
                if not self._should_scrape_symbol(symbol):
                    continue

                bid = Decimal(str(ticker_dict.get("bidPrice", 0)))
                ask = Decimal(str(ticker_dict.get("askPrice", 0)))
                last = Decimal(str(ticker_dict.get("lastPrice", 0)))
                volume_24h = Decimal(str(ticker_dict.get("volume", 0)))

                ticker = normalize_ticker_from_raw(
                    symbol=symbol,
                    exchange="binance",
                    bid=bid,
                    ask=ask,
                    last=last,
                    volume=volume_24h,
                )
                await self._store.update_ticker(ticker)
                count += 1

            logger.info(f"Scraped {count} tickers")
            return count
        except Exception as e:
            logger.error(f"Failed to scrape tickers: {e}")
            return 0

    async def scrape_ohlcv(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> int:
        """Fetch klines for a symbol and upsert into database.

        Returns number of bars inserted/updated.
        """
        try:
            klines = await self._client.get_klines(
                symbol=symbol, interval=interval, limit=limit
            )
            count = 0

            async with self._session_factory() as session:
                for kline in klines:
                    if len(kline) < 11:
                        continue

                    open_time_ms = int(kline[0])
                    open_price = Decimal(str(kline[1]))
                    high = Decimal(str(kline[2]))
                    low = Decimal(str(kline[3]))
                    close = Decimal(str(kline[4]))
                    volume = Decimal(str(kline[7]))
                    close_time_ms = int(kline[6])
                    quote_volume = Decimal(str(kline[7]))
                    trades = int(kline[8])

                    open_time = datetime.fromtimestamp(
                        open_time_ms / 1000.0, tz=timezone.utc
                    )
                    close_time = datetime.fromtimestamp(
                        close_time_ms / 1000.0, tz=timezone.utc
                    )

                    # Check if bar already exists
                    existing = await session.execute(
                        select(OHLCVBar).where(
                            OHLCVBar.symbol == symbol,
                            OHLCVBar.interval == interval,
                            OHLCVBar.open_time == open_time,
                        )
                    )
                    bar = existing.scalar_one_or_none()

                    if bar:
                        # Update existing
                        bar.open = open_price
                        bar.high = high
                        bar.low = low
                        bar.close = close
                        bar.volume = volume
                        bar.quote_volume = quote_volume
                        bar.trades = trades
                    else:
                        # Create new
                        bar = OHLCVBar(
                            symbol=symbol,
                            interval=interval,
                            open_time=open_time,
                            open=open_price,
                            high=high,
                            low=low,
                            close=close,
                            volume=volume,
                            close_time=close_time,
                            quote_volume=quote_volume,
                            trades=trades,
                        )
                        session.add(bar)

                    count += 1

                await session.commit()

            logger.info(f"Scraped {count} OHLCV bars for {symbol}/{interval}")
            return count
        except Exception as e:
            logger.error(f"Failed to scrape OHLCV for {symbol}/{interval}: {e}")
            return 0

    async def run_cycle(self) -> None:
        """Execute a full scrape cycle: tickers + OHLCV for configured symbols."""
        logger.info("Starting scrape cycle")

        # Scrape all tickers first
        await self.scrape_tickers()

        # Then scrape OHLCV for configured symbols
        symbols = self._settings.scraper_symbols_list
        intervals = self._settings.scraper_ohlcv_intervals_list
        limit = self._settings.SCRAPER_OHLCV_LIMIT

        for symbol in symbols:
            for interval in intervals:
                await self.scrape_ohlcv(symbol, interval, limit)
                await asyncio.sleep(0.1)  # Small delay between requests

        logger.info("Scrape cycle complete")

    async def start(self) -> None:
        """Start background scraper loop."""
        if self._running:
            logger.warning("Scraper already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Market scraper started")

    async def stop(self) -> None:
        """Stop background scraper loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Market scraper stopped")

    async def _run_loop(self) -> None:
        """Main loop: run cycles at configurable interval."""
        interval = self._settings.SCRAPER_INTERVAL_SECONDS
        try:
            while self._running:
                await self.run_cycle()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Scraper loop error: {e}")

    def _should_scrape_symbol(self, symbol: str) -> bool:
        """Check if symbol should be scraped."""
        whitelist = self._settings.symbol_whitelist_set
        if whitelist and symbol not in whitelist:
            return False
        return True

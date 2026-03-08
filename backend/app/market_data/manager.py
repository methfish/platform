"""
Market data manager - orchestrates market data subscriptions and distribution.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from app.core.events import EventBus, MarketDataUpdate, AlertTriggered
from app.exchange.base import ExchangeAdapter
from app.exchange.models import NormalizedTicker
from app.market_data.store import MarketDataStore

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Manages market data subscriptions and distributes updates.

    Subscribes to exchange ticker streams, stores in Redis,
    and publishes to the internal event bus.
    """

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        store: MarketDataStore,
        event_bus: EventBus,
        stale_threshold_seconds: int = 30,
    ):
        self._adapter = exchange_adapter
        self._store = store
        self._event_bus = event_bus
        self._stale_threshold = stale_threshold_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self, symbols: list[str]) -> None:
        """Start subscribing to market data for the given symbols."""
        if self._running:
            logger.warning("MarketDataManager already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run(symbols))
        logger.info(f"Market data manager started for {len(symbols)} symbols")

    async def stop(self) -> None:
        """Stop the market data subscription."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Market data manager stopped")

    async def _run(self, symbols: list[str]) -> None:
        """Main loop: subscribe and process ticker updates."""
        try:
            async for ticker in self._adapter.subscribe_ticker(symbols):
                if not self._running:
                    break

                await self._process_ticker(ticker)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Market data stream error: {e}")
            await self._event_bus.publish(AlertTriggered(
                severity="WARNING",
                source="market_data",
                message=f"Market data stream error: {e}",
            ))

    async def _process_ticker(self, ticker: NormalizedTicker) -> None:
        """Process a single ticker update."""
        # Store in cache
        await self._store.update_ticker(ticker)

        # Update paper adapter prices if applicable
        if hasattr(self._adapter, 'update_market_price'):
            self._adapter.update_market_price(
                ticker.symbol, ticker.bid, ticker.ask, ticker.last
            )

        # Publish to event bus
        await self._event_bus.publish(MarketDataUpdate(
            symbol=ticker.symbol,
            bid=ticker.bid,
            ask=ticker.ask,
            last=ticker.last,
            volume_24h=ticker.volume_24h,
        ))

    async def seed_paper_prices(self, prices: dict[str, Decimal]) -> None:
        """Seed initial prices for paper trading without a live feed."""
        for symbol, price in prices.items():
            ticker = NormalizedTicker(
                symbol=symbol,
                exchange="paper",
                bid=price * Decimal("0.9999"),
                ask=price * Decimal("1.0001"),
                last=price,
                timestamp=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
            await self._store.update_ticker(ticker)

            if hasattr(self._adapter, 'update_market_price'):
                self._adapter.update_market_price(
                    symbol, ticker.bid, ticker.ask, ticker.last
                )

        logger.info(f"Seeded paper prices for {len(prices)} symbols")

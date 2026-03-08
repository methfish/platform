"""
Strategy runner - manages strategy lifecycle and feeds market data.
"""

from __future__ import annotations

import logging

from app.core.enums import StrategyStatus
from app.core.events import EventBus, MarketDataUpdate
from app.strategy.base import BaseStrategy, OrderIntent
from app.strategy.context import StrategyContext

logger = logging.getLogger(__name__)


class StrategyRunner:
    """
    Manages registered strategies and routes market data to them.

    Strategies are registered with enable/disable control.
    Market data events trigger strategy.on_tick() for active strategies.
    Generated OrderIntents are collected and returned for OMS submission.
    """

    def __init__(self, event_bus: EventBus):
        self._strategies: dict[str, BaseStrategy] = {}
        self._statuses: dict[str, StrategyStatus] = {}
        self._contexts: dict[str, StrategyContext] = {}
        self._event_bus = event_bus
        self._order_callback = None

    def register_strategy(self, strategy: BaseStrategy) -> None:
        """Register a strategy (starts in PAUSED state)."""
        self._strategies[strategy.name] = strategy
        self._statuses[strategy.name] = StrategyStatus.PAUSED
        self._contexts[strategy.name] = StrategyContext()
        logger.info(f"Strategy registered: {strategy.name} ({strategy.strategy_type})")

    async def enable_strategy(self, name: str) -> None:
        """Enable a strategy to start receiving market data."""
        if name not in self._strategies:
            raise ValueError(f"Strategy not found: {name}")
        self._statuses[name] = StrategyStatus.ACTIVE
        await self._strategies[name].on_start()
        logger.info(f"Strategy enabled: {name}")

    async def disable_strategy(self, name: str) -> None:
        """Disable a strategy."""
        if name not in self._strategies:
            raise ValueError(f"Strategy not found: {name}")
        self._statuses[name] = StrategyStatus.PAUSED
        await self._strategies[name].on_stop()
        logger.info(f"Strategy disabled: {name}")

    def set_order_callback(self, callback) -> None:
        """Set callback for order intents: async fn(OrderIntent) -> None."""
        self._order_callback = callback

    async def on_market_data(self, event: MarketDataUpdate) -> None:
        """Process market data update - feed to active strategies."""
        for name, strategy in self._strategies.items():
            if self._statuses.get(name) != StrategyStatus.ACTIVE:
                continue

            ctx = self._contexts[name]
            try:
                intents = await strategy.on_tick(
                    event.symbol, event.bid, event.ask, event.last
                )
                for intent in intents:
                    intent.strategy_id = name
                    if self._order_callback:
                        await self._order_callback(intent)
            except Exception as e:
                logger.error(f"Strategy {name} error on tick: {e}")
                self._statuses[name] = StrategyStatus.ERROR

    def get_strategy_status(self, name: str) -> StrategyStatus | None:
        return self._statuses.get(name)

    def list_strategies(self) -> list[dict]:
        return [
            {
                "name": name,
                "type": strategy.strategy_type,
                "status": self._statuses.get(name, StrategyStatus.STOPPED).value,
            }
            for name, strategy in self._strategies.items()
        ]

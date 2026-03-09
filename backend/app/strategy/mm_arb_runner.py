"""
Enhanced strategy runner for market-making and arbitrage strategies.

Supports multi-exchange adapter routing, active order tracking,
per-strategy P&L, and background asyncio task management.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    OrderSide,
    OrderType,
    StrategyStatus,
    TimeInForce,
)
from app.core.events import EventBus, OrderFilled
from app.db.session import async_session_factory
from app.exchange.base import ExchangeAdapter
from app.exchange.models import NormalizedTicker
from app.models.strategy import Strategy
from app.oms.service import OrderManagementService
from app.strategy.arbitrage import ArbitrageConfig, ArbitrageStrategy
from app.strategy.base import BaseStrategy, OrderIntent
from app.strategy.context import StrategyContext
from app.strategy.market_making import MarketMakingConfig, MarketMakingStrategy
from app.strategy.pnl_tracker import StrategyPnL

logger = logging.getLogger(__name__)

_TICK_TIMEOUT = 5.0  # Max seconds for on_tick processing


class MMArbStrategyRunner:
    """
    Manages market-making and arbitrage strategy lifecycle.

    Subscribes to ticker feeds from one or more exchange adapters,
    routes ticks to active strategies, submits orders through the OMS,
    and tracks per-strategy P&L.
    """

    def __init__(
        self,
        oms: OrderManagementService,
        event_bus: EventBus,
        adapters: dict[str, ExchangeAdapter],
    ) -> None:
        self._oms = oms
        self._event_bus = event_bus
        self._adapters = adapters

        self._strategies: dict[str, BaseStrategy] = {}
        self._statuses: dict[str, StrategyStatus] = {}
        self._contexts: dict[str, StrategyContext] = {}
        self._strategy_db_ids: dict[str, UUID] = {}
        self._strategy_pnl: dict[str, StrategyPnL] = {}
        self._strategy_configs: dict[str, dict[str, Any]] = {}

        self._active_orders: dict[str, list[str]] = {}
        self._ticker_tasks: dict[str, asyncio.Task] = {}
        self._start_times: dict[str, datetime] = {}
        self._ticks_processed: dict[str, int] = {}
        self._orders_submitted: dict[str, int] = {}
        self._orders_filled: dict[str, int] = {}

        # Subscribe to fill events
        self._event_bus.subscribe(OrderFilled, self._on_fill_event)

    async def start_strategy(
        self,
        strategy_name: str,
        strategy_type: str,
        config: dict[str, Any],
        strategy_db_id: UUID,
        trading_mode: str = "PAPER",
    ) -> dict[str, Any]:
        """Start a strategy as a background task."""
        if strategy_name in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is already running")

        # Construct strategy instance
        strategy = self._build_strategy(strategy_name, strategy_type, config, str(strategy_db_id))

        # Register
        self._strategies[strategy_name] = strategy
        self._statuses[strategy_name] = StrategyStatus.ACTIVE
        self._contexts[strategy_name] = StrategyContext()
        self._strategy_db_ids[strategy_name] = strategy_db_id
        self._strategy_pnl[strategy_name] = StrategyPnL(strategy_name=strategy_name)
        self._strategy_configs[strategy_name] = config
        self._active_orders[strategy_name] = []
        self._start_times[strategy_name] = datetime.now(timezone.utc)
        self._ticks_processed[strategy_name] = 0
        self._orders_submitted[strategy_name] = 0
        self._orders_filled[strategy_name] = 0

        await strategy.on_start()

        # Determine which symbols and exchanges to subscribe to
        symbol = config.get("symbol", "BTCUSDT")

        if strategy_type == "ARBITRAGE":
            # Subscribe to both exchanges
            for exch_key in ("exchange_a", "exchange_b"):
                exchange_name = config.get(exch_key, "paper")
                if exchange_name in self._adapters:
                    task_key = f"{strategy_name}:{exchange_name}"
                    task = asyncio.create_task(
                        self._ticker_loop(strategy_name, exchange_name, [symbol]),
                        name=f"ticker_{task_key}",
                    )
                    self._ticker_tasks[task_key] = task
        else:
            # Market-making: subscribe to primary adapter
            primary_exchange = next(iter(self._adapters))
            task_key = f"{strategy_name}:{primary_exchange}"
            task = asyncio.create_task(
                self._ticker_loop(strategy_name, primary_exchange, [symbol]),
                name=f"ticker_{task_key}",
            )
            self._ticker_tasks[task_key] = task

        # Update DB status
        await self._update_db_status(strategy_db_id, StrategyStatus.ACTIVE)

        logger.info("Strategy '%s' started (type=%s)", strategy_name, strategy_type)
        return self.get_runtime_status(strategy_name)

    async def stop_strategy(self, strategy_name: str) -> dict[str, Any]:
        """Gracefully stop a running strategy."""
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not running")

        self._statuses[strategy_name] = StrategyStatus.PAUSED

        # Cancel ticker tasks
        tasks_to_cancel = [
            (k, t) for k, t in self._ticker_tasks.items()
            if k.startswith(f"{strategy_name}:")
        ]
        for key, task in tasks_to_cancel:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            del self._ticker_tasks[key]

        # Stop strategy
        strategy = self._strategies[strategy_name]
        await strategy.on_stop()

        status = self.get_runtime_status(strategy_name)

        # Update DB
        db_id = self._strategy_db_ids.get(strategy_name)
        if db_id:
            await self._update_db_status(db_id, StrategyStatus.PAUSED)

        # Cleanup
        del self._strategies[strategy_name]
        del self._contexts[strategy_name]

        logger.info("Strategy '%s' stopped", strategy_name)
        return status

    async def stop_all(self) -> None:
        """Stop all running strategies."""
        names = list(self._strategies.keys())
        for name in names:
            try:
                await self.stop_strategy(name)
            except Exception:
                logger.exception("Error stopping strategy %s", name)

    def get_runtime_status(self, strategy_name: str) -> dict[str, Any]:
        """Get real-time strategy status."""
        status = self._statuses.get(strategy_name, StrategyStatus.STOPPED)
        pnl = self._strategy_pnl.get(strategy_name)
        start_time = self._start_times.get(strategy_name)

        uptime = None
        if start_time and status == StrategyStatus.ACTIVE:
            uptime = (datetime.now(timezone.utc) - start_time).total_seconds()

        strategy = self._strategies.get(strategy_name)
        inventory = {}
        if strategy:
            if isinstance(strategy, MarketMakingStrategy):
                inventory = {strategy._config.symbol: str(strategy._current_inventory)}
            elif isinstance(strategy, ArbitrageStrategy):
                inventory = {strategy._config.symbol: str(strategy._net_inventory)}

        return {
            "name": strategy_name,
            "status": status.value,
            "strategy_type": strategy.strategy_type if strategy else "",
            "uptime_seconds": uptime,
            "ticks_processed": self._ticks_processed.get(strategy_name, 0),
            "orders_submitted": self._orders_submitted.get(strategy_name, 0),
            "orders_filled": self._orders_filled.get(strategy_name, 0),
            "active_orders": len(self._active_orders.get(strategy_name, [])),
            "current_inventory": inventory,
            "pnl": pnl.to_dict() if pnl else None,
        }

    def list_running(self) -> list[dict[str, Any]]:
        """List all running strategies with status."""
        return [self.get_runtime_status(name) for name in self._strategies]

    # --- Internal ---

    def _build_strategy(
        self, name: str, strategy_type: str, config: dict[str, Any], strategy_id: str
    ) -> BaseStrategy:
        """Construct a strategy instance from type and config."""
        if strategy_type == "MARKET_MAKING":
            mm_config = MarketMakingConfig.from_dict(config)
            return MarketMakingStrategy(config=mm_config, strategy_id=strategy_id)
        elif strategy_type == "ARBITRAGE":
            arb_config = ArbitrageConfig.from_dict(config)
            return ArbitrageStrategy(config=arb_config, strategy_id=strategy_id)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    async def _ticker_loop(
        self, strategy_name: str, exchange_name: str, symbols: list[str]
    ) -> None:
        """Background task: subscribe to tickers and dispatch to strategy."""
        adapter = self._adapters.get(exchange_name)
        if not adapter:
            logger.error("No adapter for exchange '%s'", exchange_name)
            return

        try:
            async for ticker in adapter.subscribe_ticker(symbols):
                if self._statuses.get(strategy_name) != StrategyStatus.ACTIVE:
                    break

                try:
                    await asyncio.wait_for(
                        self._dispatch_tick(strategy_name, exchange_name, ticker),
                        timeout=_TICK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("Strategy '%s' tick timeout", strategy_name)
                except Exception:
                    logger.exception("Strategy '%s' tick error", strategy_name)
                    self._statuses[strategy_name] = StrategyStatus.ERROR
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Ticker loop error for '%s'", strategy_name)
            self._statuses[strategy_name] = StrategyStatus.ERROR

    async def _dispatch_tick(
        self, strategy_name: str, exchange_name: str, ticker: NormalizedTicker
    ) -> None:
        """Dispatch a tick to a strategy and process resulting intents."""
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            return

        ctx = self._contexts.get(strategy_name)
        if ctx:
            ctx.update_ticker(ticker)

        # For arb strategies, update exchange-specific ticker
        if isinstance(strategy, ArbitrageStrategy):
            strategy.update_exchange_ticker(
                exchange_name, ticker.bid, ticker.ask, ticker.last
            )

        self._ticks_processed[strategy_name] = self._ticks_processed.get(strategy_name, 0) + 1

        # Call strategy
        intents = await strategy.on_tick(
            symbol=ticker.symbol,
            bid=ticker.bid,
            ask=ticker.ask,
            last=ticker.last,
        )

        # Execute intents
        for intent in intents:
            if intent.metadata.get("action") == "cancel_all":
                # Handle cancel-and-replace
                continue

            if intent.quantity <= 0:
                continue

            await self._execute_intent(strategy_name, intent)

    async def _execute_intent(self, strategy_name: str, intent: OrderIntent) -> None:
        """Submit an order intent through the OMS."""
        try:
            # Determine which adapter to use
            target_exchange = intent.exchange or next(iter(self._adapters))
            adapter = self._adapters.get(target_exchange)
            if not adapter:
                logger.warning("No adapter for exchange '%s'", target_exchange)
                return

            # Create a temporary OMS with the target adapter if different
            oms = self._oms
            if adapter != self._oms.exchange_adapter:
                oms = OrderManagementService(
                    exchange_adapter=adapter,
                    risk_engine=self._oms.risk_engine,
                    event_bus=self._event_bus,
                )

            strategy_uuid = self._strategy_db_ids.get(strategy_name)

            async with async_session_factory() as session:
                order = await oms.submit_order(
                    symbol=intent.symbol,
                    side=intent.side,
                    order_type=intent.order_type,
                    quantity=intent.quantity,
                    price=intent.price,
                    strategy_id=strategy_uuid,
                    time_in_force=intent.time_in_force,
                    session=session,
                )
                self._orders_submitted[strategy_name] = (
                    self._orders_submitted.get(strategy_name, 0) + 1
                )
                self._active_orders.setdefault(strategy_name, []).append(
                    order.client_order_id
                )

        except Exception:
            logger.exception(
                "Failed to execute intent for '%s': %s %s %s",
                strategy_name, intent.side.value, intent.quantity, intent.symbol,
            )

    async def _on_fill_event(self, event: OrderFilled) -> None:
        """Handle fill events from the event bus."""
        # Find which strategy this fill belongs to
        for name, order_ids in self._active_orders.items():
            # Match by checking strategy existence (simplified)
            strategy = self._strategies.get(name)
            if strategy and event.symbol:
                pnl = self._strategy_pnl.get(name)
                if pnl:
                    pnl.record_fill(
                        side=event.side,
                        quantity=event.quantity,
                        price=event.price,
                        commission=event.commission,
                    )

                self._orders_filled[name] = self._orders_filled.get(name, 0) + 1

                await strategy.on_fill(
                    symbol=event.symbol,
                    side=event.side,
                    quantity=event.quantity,
                    price=event.price,
                )
                break

    async def _update_db_status(self, strategy_id: UUID, status: StrategyStatus) -> None:
        """Update strategy status in database."""
        try:
            async with async_session_factory() as session:
                await session.execute(
                    update(Strategy)
                    .where(Strategy.id == strategy_id)
                    .values(status=status.value)
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update strategy status in DB")

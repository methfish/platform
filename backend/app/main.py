"""
Pensy Order Execution Platform - FastAPI Application.

This is the main entry point. The application boots in PAPER trading mode
by default. Live trading requires explicit configuration and operator
confirmation at runtime.

WARNING: If LIVE_TRADING_ENABLED is true, a startup warning is logged.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.enums import ExchangeName, TradingMode
from app.db.session import close_db, init_db, init_db_async
from app.market_data.seeder import seed_simulated_tickers
from app.dependencies import get_trading_state, set_exchange_adapter, set_mm_arb_runner
from app.exchange.factory import create_exchange_adapter
from app.observability.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    settings = get_settings()

    # Setup logging
    setup_logging(settings.LOG_LEVEL, settings.APP_ENV.value)

    # Log sanitized config
    logger.info("=" * 60)
    logger.info("PENSY ORDER EXECUTION PLATFORM")
    logger.info("=" * 60)
    config_summary = settings.get_sanitized_config()
    for key, value in config_summary.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    # CRITICAL SAFETY WARNING
    if settings.LIVE_TRADING_ENABLED:
        logger.warning("!" * 60)
        logger.warning("!!! LIVE TRADING IS ENABLED IN CONFIGURATION !!!")
        logger.warning("!!! Operator must still confirm via admin API  !!!")
        logger.warning("!" * 60)
    else:
        logger.info("Trading mode: PAPER (default, safe)")

    # Initialize database
    init_db()
    await init_db_async()
    logger.info("Database connection initialized")

    # Create exchange adapter (paper by default)
    trading_mode = TradingMode.PAPER  # Always start in paper mode
    adapter = create_exchange_adapter(
        ExchangeName.PAPER, settings, trading_mode
    )
    await adapter.connect()
    set_exchange_adapter(adapter)
    logger.info(f"Exchange adapter: {adapter.exchange_name} (paper={adapter.is_paper})")

    # Seed simulated market data for forex and stocks
    await seed_simulated_tickers()
    logger.info("Simulated forex & stock tickers seeded")

    # Initialize strategy runner (MM/Arb engine)
    from app.core.events import event_bus
    from app.oms.service import OrderManagementService
    from app.risk.engine import RiskEngine

    risk_engine = RiskEngine()
    oms = OrderManagementService(
        exchange_adapter=adapter,
        risk_engine=risk_engine,
        event_bus=event_bus,
    )

    from app.strategy.mm_arb_runner import MMArbStrategyRunner

    mm_arb_runner = MMArbStrategyRunner(
        oms=oms,
        event_bus=event_bus,
        adapters={"paper": adapter},
    )
    set_mm_arb_runner(mm_arb_runner)
    logger.info("Strategy engine initialized (MM/Arb runner ready)")

    logger.info("Pensy platform startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Pensy platform...")
    await mm_arb_runner.stop_all()
    await adapter.disconnect()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Pensy Order Execution Platform",
        description="Proprietary order execution platform for crypto trading",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routers
    from app.api.router import api_router
    app.include_router(api_router)

    return app


app = create_app()

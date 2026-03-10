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
from app.dependencies import (
    get_trading_state,
    set_exchange_adapter,
    set_fill_handler,
    set_mm_arb_runner,
    set_oms_service,
    set_position_tracker,
    set_risk_engine,
)
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

    # Also seed prices into paper adapter's in-memory book for order fills
    if hasattr(adapter, '_book'):
        from app.market_data.seeder import FOREX_SYMBOLS, STOCK_SYMBOLS
        from decimal import Decimal as D
        for symbol, (bid, ask, last, _vol) in {**FOREX_SYMBOLS, **STOCK_SYMBOLS}.items():
            adapter._book.update_price(symbol, D(bid), D(ask), D(last))
        logger.info("Seeded %d prices into paper adapter", len(FOREX_SYMBOLS) + len(STOCK_SYMBOLS))
    logger.info("Simulated forex & stock tickers seeded")

    # Initialize core trading services
    from app.core.events import event_bus
    from app.oms.service import OrderManagementService
    from app.oms.fill_handler import FillHandler
    from app.position.tracker import PositionTracker
    from app.risk.engine import RiskEngine

    # Risk engine with production checks
    from app.risk.checks.kill_switch import KillSwitchCheck
    from app.risk.checks.order_size import OrderSizeCheck
    from app.risk.checks.position_limit import PositionLimitCheck
    from app.risk.checks.daily_loss import DailyLossCheck

    risk_engine = RiskEngine(checks=[
        KillSwitchCheck(),       # Highest priority — blocks all if active
        DailyLossCheck(),        # Circuit breaker on daily loss
        OrderSizeCheck(),        # Per-order quantity/notional limit
        PositionLimitCheck(),    # Resulting position notional limit
    ])
    set_risk_engine(risk_engine)
    logger.info("Risk engine initialized with %d checks", len(risk_engine.checks))

    # OMS service
    oms = OrderManagementService(
        exchange_adapter=adapter,
        risk_engine=risk_engine,
        event_bus=event_bus,
    )
    set_oms_service(oms)

    # Position tracker + fill handler
    position_tracker = PositionTracker()
    set_position_tracker(position_tracker)

    fill_handler = FillHandler(
        event_bus=event_bus,
        position_tracker=position_tracker,
    )
    set_fill_handler(fill_handler)
    logger.info("OMS, position tracker, and fill handler initialized")

    # Strategy runner
    from app.strategy.mm_arb_runner import MMArbStrategyRunner

    mm_arb_runner = MMArbStrategyRunner(
        oms=oms,
        event_bus=event_bus,
        adapters={"paper": adapter},
    )
    set_mm_arb_runner(mm_arb_runner)
    logger.info("Strategy engine initialized (MM/Arb runner ready)")

    # --- Background tasks ---
    import asyncio
    from app.db.session import async_session_factory as _session_factory

    async def _fill_listener():
        """Listen for exchange fill events and process through FillHandler."""
        logger.info("Fill listener started")
        try:
            async for user_event in adapter.subscribe_user_data():
                if user_event.event_type != "FILL":
                    continue
                try:
                    async with _session_factory() as session:
                        await fill_handler.process_fill_by_client_order_id(
                            client_order_id=user_event.client_order_id,
                            fill_quantity=user_event.filled_quantity,
                            fill_price=user_event.fill_price,
                            session=session,
                            commission=user_event.commission,
                            commission_asset=user_event.commission_asset or None,
                            exchange_fill_id=user_event.exchange_order_id,
                            fill_time=user_event.timestamp,
                        )
                        await session.commit()
                        logger.debug(
                            "Fill processed: %s qty=%s @ %s",
                            user_event.client_order_id,
                            user_event.filled_quantity,
                            user_event.fill_price,
                        )
                except Exception:
                    logger.exception("Error processing fill event: %s", user_event)
        except asyncio.CancelledError:
            logger.info("Fill listener stopped")
        except Exception:
            logger.exception("Fill listener crashed")

    async def _mark_to_market_loop():
        """Periodically update unrealized PnL for all open positions."""
        logger.info("Mark-to-market loop started (interval=5s)")
        try:
            while True:
                await asyncio.sleep(5)
                try:
                    async with _session_factory() as session:
                        positions = await position_tracker.get_all_positions(session)
                        for pos in positions:
                            ticker = adapter._book.get_price(pos.symbol) if hasattr(adapter, '_book') else None
                            if ticker and ticker.last > 0:
                                position_tracker.update_unrealized_pnl(pos, ticker.last)
                        if positions:
                            await session.commit()
                except Exception:
                    logger.exception("Mark-to-market update failed")
        except asyncio.CancelledError:
            logger.info("Mark-to-market loop stopped")

    # Start background tasks
    fill_task = asyncio.create_task(_fill_listener(), name="fill_listener")
    mtm_task = asyncio.create_task(_mark_to_market_loop(), name="mark_to_market")

    # Initialize Agent System
    from app.agents.skill_registry import SkillRegistry
    from app.agents.skill_executor import SkillExecutor
    from app.db.session import async_session_factory

    skill_registry = SkillRegistry()
    skill_executor = SkillExecutor(session_factory=async_session_factory)

    from app.agents.types import AgentType

    # Register Research Agent skills
    from app.agents.research_agent.skills.data_inventory import DataInventorySkill
    from app.agents.research_agent.skills.data_collection import DataCollectionSkill
    from app.agents.research_agent.skills.backtest_execution import BacktestExecutionSkill
    from app.agents.research_agent.skills.result_analysis import ResultAnalysisSkill
    from app.agents.research_agent.skills.parameter_optimization import ParameterOptimizationSkill
    from app.agents.research_agent.skills.report_generation import ReportGenerationSkill

    research_skills = [
        DataInventorySkill(), DataCollectionSkill(), BacktestExecutionSkill(),
        ResultAnalysisSkill(), ParameterOptimizationSkill(), ReportGenerationSkill(),
    ]
    for s in research_skills:
        skill_registry.register(s, [AgentType.RESEARCH])

    # Register Strategy Coding Agent skills
    from app.agents.coding_agent.skills.strategy_analysis import StrategyAnalysisSkill
    from app.agents.coding_agent.skills.code_generation import CodeGenerationSkill
    from app.agents.coding_agent.skills.code_validation import CodeValidationSkill
    from app.agents.coding_agent.skills.backtest_verification import BacktestVerificationSkill
    from app.agents.coding_agent.skills.code_registration import CodeRegistrationSkill

    coding_skills = [
        StrategyAnalysisSkill(), CodeGenerationSkill(), CodeValidationSkill(),
        BacktestVerificationSkill(), CodeRegistrationSkill(),
    ]
    for s in coding_skills:
        skill_registry.register(s, [AgentType.STRATEGY_CODING])

    # Create agents
    from app.agents.research_agent import ResearchAgent
    from app.agents.coding_agent import StrategyCodingAgent

    research_agent = ResearchAgent(registry=skill_registry, executor=skill_executor)
    coding_agent = StrategyCodingAgent(registry=skill_registry, executor=skill_executor)

    # Build agent registry
    from app.dependencies import set_agent_registry
    agent_reg = {
        AgentType.RESEARCH.value: research_agent,
        AgentType.STRATEGY_CODING.value: coding_agent,
    }
    set_agent_registry(agent_reg)
    logger.info("Agent system initialized: %d agents, %d skills", len(agent_reg), len(skill_registry.list_all()))

    # Load generated strategies from DB
    from app.backtest.strategy_loader import load_strategies_from_db
    loaded = await load_strategies_from_db(async_session_factory)
    logger.info("Loaded %d generated strategies from database", loaded)

    logger.info("Pensy platform startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Pensy platform...")
    fill_task.cancel()
    mtm_task.cancel()
    await asyncio.gather(fill_task, mtm_task, return_exceptions=True)
    await mm_arb_runner.stop_all()
    await adapter.disconnect()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Pensy Order Execution Platform",
        description="Proprietary order execution platform for forex & stock trading",
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

    # Register error handlers and request middleware
    from app.api.middleware import register_middleware
    register_middleware(app)

    # Import and include routers
    from app.api.router import api_router
    app.include_router(api_router)

    return app


app = create_app()

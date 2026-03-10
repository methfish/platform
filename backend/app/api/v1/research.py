"""
Research API — data collection, backtesting, metrics, and parameter sweeps.

Endpoints:
  POST /research/collect         — Start data collection job
  GET  /research/collect/status  — Collection status
  GET  /research/data/summary    — Stored data summary
  POST /research/backtest        — Run a backtest
  GET  /research/backtests       — List backtest results
  GET  /research/backtest/{id}   — Get backtest detail
  POST /research/sweep           — Parameter sweep
  GET  /research/dashboard       — Aggregated research dashboard
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

# Maximum bars loaded into memory for a single backtest/sweep.
# Prevents OOM on large datasets. 500K 1-min bars ≈ 1 year of forex data.
MAX_BARS_PER_QUERY = 500_000

from app.api.schemas.research import (
    BacktestListItem,
    BacktestRequest,
    BacktestResponse,
    DataCollectionRequest,
    DataCollectionStatus,
    DataSummaryResponse,
    ParameterSweepRequest,
    ParameterSweepResponse,
    ResearchDashboardResponse,
    SweepResultItem,
)
from app.auth.jwt import get_current_user
from app.backtest.costs import (
    CONSERVATIVE,
    FOREX_ECN,
    FOREX_RETAIL,
    STOCK_IB,
    STOCK_RETAIL,
    ZERO_COST,
    CostModel,
)
from app.backtest.engine import BacktestConfig, BacktestEngine, Bar, run_parameter_sweep
from app.data.collector import CollectionJob, MarketDataCollector
from app.db.session import get_session
from app.models.backtest import BacktestRun
from app.models.market_data import OHLCVBar

logger = logging.getLogger("pensy.api.research")

router = APIRouter(prefix="/research", tags=["research"])

# Global collector instance (shared across requests)
_collector: MarketDataCollector | None = None
_collection_task: asyncio.Task | None = None

COST_MODELS: dict[str, CostModel] = {
    "forex": FOREX_RETAIL,
    "forex_ecn": FOREX_ECN,
    "stock": STOCK_RETAIL,
    "stock_ib": STOCK_IB,
    "conservative": CONSERVATIVE,
    "zero": ZERO_COST,
}


# ---------------------------------------------------------------------------
# Data Collection
# ---------------------------------------------------------------------------

@router.post(
    "/collect",
    response_model=DataCollectionStatus,
    summary="Start a data collection job",
)
async def start_collection(
    body: DataCollectionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> DataCollectionStatus:
    """Kick off an async data collection job using yfinance."""
    global _collector, _collection_task

    if _collector and _collector.status.status == "running":
        raise HTTPException(409, "A collection job is already running")

    _collector = MarketDataCollector()

    job = CollectionJob(
        exchange_id=body.exchange,
        symbols=body.symbols,
        intervals=body.intervals,
        limit=body.limit,
    )

    async def _run_collection():
        try:
            from app.db.session import async_session_factory
            async with async_session_factory() as coll_session:
                await _collector.collect(job, coll_session)
        except Exception as exc:
            logger.exception("Collection job failed: %s", exc)
        finally:
            await _collector.close()

    # Run in background
    _collection_task = asyncio.create_task(_run_collection())

    # Return initial status
    status = _collector.status
    return DataCollectionStatus(
        job_id=status.job_id or "pending",
        exchange=body.exchange,
        status="starting",
        symbols_total=len(body.symbols) * len(body.intervals),
        symbols_done=0,
        bars_inserted=0,
        bars_skipped=0,
        errors=[],
        progress_pct=0.0,
    )


@router.get(
    "/collect/status",
    response_model=DataCollectionStatus,
    summary="Check data collection status",
)
async def collection_status(
    _user=Depends(get_current_user),
) -> DataCollectionStatus:
    """Get the current status of the running collection job."""
    if _collector is None:
        return DataCollectionStatus(
            job_id="none",
            exchange="",
            status="idle",
            symbols_total=0,
            symbols_done=0,
            bars_inserted=0,
            bars_skipped=0,
            errors=[],
            progress_pct=0.0,
        )

    s = _collector.status
    return DataCollectionStatus(
        job_id=s.job_id,
        exchange=s.exchange,
        status=s.status,
        symbols_total=s.symbols_total,
        symbols_done=s.symbols_done,
        bars_inserted=s.bars_inserted,
        bars_skipped=s.bars_skipped,
        errors=s.errors,
        progress_pct=s.progress_pct,
        started_at=s.started_at,
        completed_at=s.completed_at,
    )


@router.get(
    "/data/summary",
    response_model=DataSummaryResponse,
    summary="Get stored data summary",
)
async def data_summary(
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> DataSummaryResponse:
    """Return summary of all stored OHLCV data."""
    collector = MarketDataCollector()
    summary = await collector.get_data_summary(session)
    return DataSummaryResponse(**summary)


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------

@router.post(
    "/backtest",
    response_model=BacktestResponse,
    summary="Run a backtest",
)
async def run_backtest(
    body: BacktestRequest,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> BacktestResponse:
    """
    Run a backtest against stored OHLCV data.

    Fetches bars from the database, runs the strategy engine,
    and persists the result.
    """
    # Load bars from DB
    query = select(OHLCVBar).where(
        OHLCVBar.symbol == body.symbol,
        OHLCVBar.interval == body.interval,
    )
    if body.start_date:
        query = query.where(OHLCVBar.open_time >= body.start_date)
    if body.end_date:
        query = query.where(OHLCVBar.open_time <= body.end_date)
    query = query.order_by(OHLCVBar.open_time).limit(MAX_BARS_PER_QUERY)

    result = await session.execute(query)
    db_bars = result.scalars().all()

    if not db_bars:
        raise HTTPException(404, f"No OHLCV data for {body.symbol} {body.interval}")

    # Convert to backtest bars
    bars = [
        Bar(
            timestamp=b.open_time,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
            symbol=body.symbol,
            interval=body.interval,
        )
        for b in db_bars
    ]

    # Select cost model
    cost_model = COST_MODELS.get(body.cost_model, FOREX_RETAIL)

    config = BacktestConfig(
        strategy_type=body.strategy_type,
        symbol=body.symbol,
        interval=body.interval,
        initial_capital=body.initial_capital,
        cost_model=cost_model,
        strategy_params=body.strategy_params,
        max_position_size=body.max_position_size,
        stop_loss_pct=body.stop_loss_pct,
        take_profit_pct=body.take_profit_pct,
    )

    # Run backtest (synchronous — typically fast enough for <50k bars)
    engine = BacktestEngine(config)
    bt_result = engine.run(bars)

    # Persist to DB
    run = BacktestRun(
        strategy_type=body.strategy_type,
        symbol=body.symbol,
        interval=body.interval,
        initial_capital=body.initial_capital,
        status=bt_result.status,
        strategy_params=body.strategy_params,
        cost_model_name=body.cost_model,
        total_trades=len(bt_result.trades),
        total_bars=bt_result.total_bars,
        error=bt_result.error,
        started_at=bt_result.run_at,
        completed_at=datetime.now(timezone.utc),
    )

    if bt_result.metrics:
        m = bt_result.metrics
        run.net_pnl = m.total_net_pnl
        run.gross_pnl = m.total_gross_pnl
        run.sharpe_ratio = Decimal(str(round(m.sharpe_ratio, 6)))
        run.max_drawdown_pct = Decimal(str(round(m.max_drawdown_pct, 6)))
        run.win_rate = Decimal(str(round(m.win_rate, 6)))
        run.profit_factor = Decimal(str(round(min(m.profit_factor, 999999), 6)))
        run.expectancy = m.expectancy
        run.total_commission = m.total_commission
        run.fee_drag_pct = Decimal(str(round(m.fee_drag_pct, 6)))
        run.trades_per_day = Decimal(str(round(m.trades_per_day, 4)))
        run.metrics_json = m.to_dict()
        run.equity_curve_json = [
            {"t": ep.timestamp.isoformat(), "eq": str(ep.equity), "dd": round(ep.drawdown_pct, 4)}
            for ep in m.equity_curve
        ]
        run.is_trustworthy = m.is_trustworthy
        run.trust_issues = m.trust_issues

    session.add(run)
    await session.commit()
    await session.refresh(run)

    return BacktestResponse(**bt_result.to_dict())


@router.get(
    "/backtests",
    response_model=list[BacktestListItem],
    summary="List backtest runs",
)
async def list_backtests(
    limit: int = 50,
    strategy_type: str | None = None,
    symbol: str | None = None,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> list[BacktestListItem]:
    """List recent backtest runs, optionally filtered."""
    query = select(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(limit)

    if strategy_type:
        query = query.where(BacktestRun.strategy_type == strategy_type)
    if symbol:
        query = query.where(BacktestRun.symbol == symbol)

    result = await session.execute(query)
    runs = result.scalars().all()

    return [
        BacktestListItem(
            id=str(r.id),
            strategy_type=r.strategy_type,
            symbol=r.symbol,
            interval=r.interval,
            status=r.status,
            total_trades=r.total_trades,
            net_pnl=str(r.net_pnl),
            sharpe_ratio=str(r.sharpe_ratio),
            max_drawdown_pct=str(r.max_drawdown_pct),
            win_rate=str(r.win_rate),
            is_trustworthy=r.is_trustworthy,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get(
    "/backtest/{backtest_id}",
    summary="Get backtest detail",
)
async def get_backtest(
    backtest_id: str,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> dict:
    """Get full backtest result with metrics and equity curve."""
    from uuid import UUID
    result = await session.execute(
        select(BacktestRun).where(BacktestRun.id == UUID(backtest_id))
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "Backtest not found")

    return {
        "id": str(run.id),
        "strategy_type": run.strategy_type,
        "symbol": run.symbol,
        "interval": run.interval,
        "status": run.status,
        "strategy_params": run.strategy_params,
        "cost_model": run.cost_model_name,
        "initial_capital": str(run.initial_capital),
        "total_trades": run.total_trades,
        "total_bars": run.total_bars,
        "metrics": run.metrics_json,
        "equity_curve": run.equity_curve_json,
        "is_trustworthy": run.is_trustworthy,
        "trust_issues": run.trust_issues,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Parameter Sweep
# ---------------------------------------------------------------------------

@router.post(
    "/sweep",
    response_model=ParameterSweepResponse,
    summary="Run parameter sweep",
)
async def parameter_sweep(
    body: ParameterSweepRequest,
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> ParameterSweepResponse:
    """
    Sweep over parameter combinations and rank by robustness score.
    """
    # Load bars
    query = (
        select(OHLCVBar)
        .where(OHLCVBar.symbol == body.symbol, OHLCVBar.interval == body.interval)
        .order_by(OHLCVBar.open_time)
        .limit(MAX_BARS_PER_QUERY)
    )
    result = await session.execute(query)
    db_bars = result.scalars().all()

    if not db_bars:
        raise HTTPException(404, f"No OHLCV data for {body.symbol} {body.interval}")

    bars = [
        Bar(
            timestamp=b.open_time,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
            symbol=body.symbol,
        )
        for b in db_bars
    ]

    sweep_results = run_parameter_sweep(
        bars=bars,
        strategy_type=body.strategy_type,
        symbol=body.symbol,
        param_grid=body.param_grid,
        initial_capital=body.initial_capital,
        max_position_size=body.max_position_size,
    )

    return ParameterSweepResponse(
        strategy_type=body.strategy_type,
        symbol=body.symbol,
        total_combinations=len(sweep_results),
        results=[
            SweepResultItem(
                params=r.params,
                sharpe_ratio=round(r.metrics.sharpe_ratio, 4),
                net_pnl=str(r.metrics.total_net_pnl),
                max_drawdown_pct=round(r.metrics.max_drawdown_pct, 4),
                win_rate=round(r.metrics.win_rate, 4),
                total_trades=r.metrics.total_trades,
                profit_factor=round(min(r.metrics.profit_factor, 9999), 4),
                rank_score=round(r.rank_score, 4),
                is_trustworthy=r.metrics.is_trustworthy,
            )
            for r in sweep_results[:20]  # Top 20
        ],
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=ResearchDashboardResponse,
    summary="Research dashboard overview",
)
async def research_dashboard(
    session: AsyncSession = Depends(get_session),
    _user=Depends(get_current_user),
) -> ResearchDashboardResponse:
    """Aggregated view for the quant research dashboard."""
    from sqlalchemy import func

    # Data summary
    collector = MarketDataCollector()
    data_summary = await collector.get_data_summary(session)

    # Count backtests
    bt_count_result = await session.execute(
        select(func.count(BacktestRun.id))
    )
    total_backtests = bt_count_result.scalar() or 0

    # Recent backtests
    recent_result = await session.execute(
        select(BacktestRun).order_by(desc(BacktestRun.created_at)).limit(10)
    )
    recent_runs = recent_result.scalars().all()

    recent_backtests = [
        BacktestListItem(
            id=str(r.id),
            strategy_type=r.strategy_type,
            symbol=r.symbol,
            interval=r.interval,
            status=r.status,
            total_trades=r.total_trades,
            net_pnl=str(r.net_pnl),
            sharpe_ratio=str(r.sharpe_ratio),
            max_drawdown_pct=str(r.max_drawdown_pct),
            win_rate=str(r.win_rate),
            is_trustworthy=r.is_trustworthy,
            created_at=r.created_at,
        )
        for r in recent_runs
    ]

    # Best Sharpe among trustworthy backtests
    best_result = await session.execute(
        select(BacktestRun)
        .where(BacktestRun.is_trustworthy == True)
        .order_by(desc(BacktestRun.sharpe_ratio))
        .limit(1)
    )
    best = best_result.scalar_one_or_none()
    best_sharpe = None
    if best:
        best_sharpe = {
            "strategy_type": best.strategy_type,
            "symbol": best.symbol,
            "sharpe": str(best.sharpe_ratio),
            "net_pnl": str(best.net_pnl),
        }

    # Active strategies (from strategy table)
    from app.models.strategy import Strategy
    active_result = await session.execute(
        select(func.count(Strategy.id)).where(Strategy.status == "ACTIVE")
    )
    active_strategies = active_result.scalar() or 0

    # Live strategy P&L (from mm_arb_runner if available)
    live_pnl = {}
    try:
        from app.dependencies import get_mm_arb_runner
        runner = get_mm_arb_runner()
        for name, pnl_tracker in runner._strategy_pnl.items():
            live_pnl[name] = str(pnl_tracker.net_pnl)
    except Exception:
        pass

    return ResearchDashboardResponse(
        data_summary=DataSummaryResponse(**data_summary),
        active_strategies=active_strategies,
        total_backtests=total_backtests,
        best_sharpe=best_sharpe,
        recent_backtests=recent_backtests,
        live_strategy_pnl=live_pnl,
    )

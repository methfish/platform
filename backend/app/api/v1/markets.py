"""Market data endpoints - overview, screener, OHLCV, heatmap."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import Settings, get_settings
from app.api.schemas.markets import (
    HeatmapEntry,
    MarketOverviewResponse,
    MoverEntry,
    OHLCVBarResponse,
    ScreenerResponse,
    SymbolAnalysisResponse,
    TickerResponse,
)
from app.db.session import get_session
from app.market_data.screener import ScreenerEngine, TrendDirection
from app.market_data.store import MarketDataStore
from app.models.market_data import OHLCVBar
from app.models.user import User

logger = logging.getLogger("pensy.api.markets")

router = APIRouter(prefix="/markets", tags=["markets"])

# Simple in-memory Redis placeholder (in production use actual Redis)
_redis_client = None


async def get_market_store() -> MarketDataStore:
    """Get market data store (Redis or in-memory fallback)."""
    return MarketDataStore(_redis_client, ttl_seconds=300)


@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview(
    current_user: User = Depends(get_current_user),
    store: MarketDataStore = Depends(get_market_store),
) -> MarketOverviewResponse:
    """Get market overview with top movers and statistics."""
    tickers = await store.get_all_tickers()

    ticker_responses = [
        TickerResponse(
            symbol=t.symbol,
            exchange=t.exchange,
            last=t.last,
            bid=t.bid,
            ask=t.ask,
            volume_24h=t.volume_24h,
            timestamp=t.timestamp,
        )
        for t in tickers
    ]

    # Sort by 24h change to find gainers/losers
    sorted_tickers = sorted(tickers, key=lambda x: x.volume_24h, reverse=True)

    # For now, use mock data for gainers/losers
    gainers = [
        MoverEntry(symbol=t.symbol, price=t.last, change_percent_24h=Decimal("5.2"), volume_24h=t.volume_24h)
        for t in sorted_tickers[:5]
    ]
    losers = [
        MoverEntry(symbol=t.symbol, price=t.last, change_percent_24h=Decimal("-3.1"), volume_24h=t.volume_24h)
        for t in sorted_tickers[-5:]
    ]

    total_vol = sum(t.volume_24h for t in tickers)
    btc = next((t for t in tickers if t.symbol == "BTCUSDT"), None)
    eth = next((t for t in tickers if t.symbol == "ETHUSDT"), None)

    return MarketOverviewResponse(
        total_symbols=len(tickers),
        total_volume_24h=total_vol,
        btc_price=btc.last if btc else None,
        eth_price=eth.last if eth else None,
        top_gainers=gainers,
        top_losers=losers,
        tickers=ticker_responses,
    )


@router.get("/symbols", response_model=ScreenerResponse)
async def list_symbols(
    trend: Optional[str] = Query(None, description="Filter by BULLISH, BEARISH, NEUTRAL"),
    min_rsi: Optional[float] = Query(None, ge=0, le=100),
    max_rsi: Optional[float] = Query(None, ge=0, le=100),
    min_volume: Optional[Decimal] = Query(None, gt=0),
    sort_by: str = Query("momentum_score", pattern="^(momentum_score|volatility_score|change_24h|price)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    store: MarketDataStore = Depends(get_market_store),
    settings: Settings = Depends(get_settings),
) -> ScreenerResponse:
    """Get paginated screener results with technical analysis."""
    # Get all OHLCV data
    all_bars = await session.execute(select(OHLCVBar).order_by(desc(OHLCVBar.open_time)))
    bars = all_bars.scalars().all()

    # Group by symbol and prepare data for screener
    symbols_data = {}
    for bar in bars:
        if bar.symbol not in symbols_data:
            symbols_data[bar.symbol] = {
                "symbol": bar.symbol,
                "closes": [],
                "highs": [],
                "lows": [],
                "volumes": [],
                "price": bar.close,
                "change_24h": Decimal("0"),  # Mock
                "volume_24h": bar.volume,
            }
        data = symbols_data[bar.symbol]
        data["closes"].append(float(bar.close))
        data["highs"].append(float(bar.high))
        data["lows"].append(float(bar.low))
        data["volumes"].append(float(bar.volume))
        data["price"] = bar.close

    # Run screener
    screener = ScreenerEngine()
    analyses = screener.screen_all(list(symbols_data.values()))

    # Apply filters
    filtered = analyses
    if trend:
        try:
            trend_enum = TrendDirection(trend.upper())
            filtered = screener.filter_symbols(filtered, trend=trend_enum)
        except ValueError:
            pass
    if min_rsi is not None or max_rsi is not None or min_volume is not None:
        filtered = screener.filter_symbols(
            filtered,
            min_rsi=min_rsi,
            max_rsi=max_rsi,
            min_volume=min_volume,
            sort_by=sort_by,
        )
    else:
        filtered = screener.filter_symbols(filtered, sort_by=sort_by)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered[start:end]

    return ScreenerResponse(
        symbols=[
            SymbolAnalysisResponse(
                symbol=a.symbol,
                price=a.price,
                change_24h=a.change_24h,
                volume_24h=a.volume_24h,
                trend=a.trend.value,
                rsi_value=a.rsi_value,
                rsi_zone=a.rsi_zone,
                volatility_score=a.volatility_score,
                momentum_score=a.momentum_score,
                volume_trend=a.volume_trend,
                signals=a.signals,
            )
            for a in page_data
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/symbols/{symbol}", response_model=SymbolAnalysisResponse)
async def get_symbol_detail(
    symbol: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    store: MarketDataStore = Depends(get_market_store),
) -> SymbolAnalysisResponse:
    """Get technical analysis for a single symbol."""
    symbol = symbol.upper()

    # Fetch OHLCV data
    bars = await session.execute(
        select(OHLCVBar)
        .where(OHLCVBar.symbol == symbol)
        .order_by(OHLCVBar.open_time)
    )
    bar_list = bars.scalars().all()

    if not bar_list:
        return SymbolAnalysisResponse(
            symbol=symbol,
            price=Decimal("0"),
            change_24h=Decimal("0"),
            volume_24h=Decimal("0"),
            trend="NEUTRAL",
            rsi_value=50.0,
            rsi_zone="Neutral",
            volatility_score=50.0,
            momentum_score=50.0,
            volume_trend="Stable",
        )

    closes = [float(b.close) for b in bar_list]
    highs = [float(b.high) for b in bar_list]
    lows = [float(b.low) for b in bar_list]
    volumes = [float(b.volume) for b in bar_list]

    price = bar_list[-1].close
    volume_24h = sum(Decimal(str(b.volume)) for b in bar_list[-24:])

    # Run screener
    screener = ScreenerEngine()
    analysis = screener.analyze_symbol(
        symbol=symbol,
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=volumes,
        price=price,
        change_24h=Decimal("0"),
        volume_24h=volume_24h,
    )

    return SymbolAnalysisResponse(
        symbol=analysis.symbol,
        price=analysis.price,
        change_24h=analysis.change_24h,
        volume_24h=analysis.volume_24h,
        trend=analysis.trend.value,
        rsi_value=analysis.rsi_value,
        rsi_zone=analysis.rsi_zone,
        volatility_score=analysis.volatility_score,
        momentum_score=analysis.momentum_score,
        volume_trend=analysis.volume_trend,
        signals=analysis.signals,
    )


@router.get("/symbols/{symbol}/ohlcv", response_model=list[OHLCVBarResponse])
async def get_symbol_ohlcv(
    symbol: str,
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OHLCVBarResponse]:
    """Get OHLCV bars for a symbol."""
    symbol = symbol.upper()

    bars = await session.execute(
        select(OHLCVBar)
        .where(OHLCVBar.symbol == symbol, OHLCVBar.interval == interval)
        .order_by(desc(OHLCVBar.open_time))
        .limit(limit)
    )
    bar_list = bars.scalars().all()

    return [OHLCVBarResponse.model_validate(b) for b in reversed(bar_list)]


@router.get("/heatmap", response_model=list[HeatmapEntry])
async def get_heatmap(
    current_user: User = Depends(get_current_user),
    store: MarketDataStore = Depends(get_market_store),
) -> list[HeatmapEntry]:
    """Get all symbols for heatmap visualization."""
    tickers = await store.get_all_tickers()

    return [
        HeatmapEntry(
            symbol=t.symbol,
            price=t.last,
            change_percent_24h=Decimal("0"),  # Mock - fetch from real data source
            volume_24h=t.volume_24h,
        )
        for t in tickers
    ]


@router.get("/movers", response_model=dict)
async def get_movers(
    current_user: User = Depends(get_current_user),
    store: MarketDataStore = Depends(get_market_store),
) -> dict:
    """Get top gainers and losers."""
    tickers = await store.get_all_tickers()

    sorted_tickers = sorted(tickers, key=lambda x: x.volume_24h, reverse=True)

    gainers = [
        MoverEntry(
            symbol=t.symbol,
            price=t.last,
            change_percent_24h=Decimal("5.2"),
            volume_24h=t.volume_24h,
        )
        for t in sorted_tickers[:10]
    ]
    losers = [
        MoverEntry(
            symbol=t.symbol,
            price=t.last,
            change_percent_24h=Decimal("-3.1"),
            volume_24h=t.volume_24h,
        )
        for t in sorted_tickers[-10:]
    ]

    return {"gainers": gainers, "losers": losers}

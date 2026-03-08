"""Pydantic v2 schemas for market data endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TickerResponse(BaseModel):
    """Single ticker snapshot."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    exchange: str
    last: Decimal
    bid: Decimal
    ask: Decimal
    volume_24h: Decimal
    change_percent_24h: Optional[Decimal] = None
    timestamp: datetime


class MoverEntry(BaseModel):
    """Top gainer/loser entry."""

    symbol: str
    price: Decimal
    change_percent_24h: Decimal
    volume_24h: Decimal


class MarketOverviewResponse(BaseModel):
    """Market overview with stats and top movers."""

    total_symbols: int
    total_volume_24h: Decimal
    btc_price: Optional[Decimal] = None
    eth_price: Optional[Decimal] = None
    top_gainers: list[MoverEntry]
    top_losers: list[MoverEntry]
    tickers: list[TickerResponse]


class SymbolAnalysisResponse(BaseModel):
    """Technical analysis for a single symbol."""

    symbol: str
    price: Decimal
    change_24h: Decimal
    volume_24h: Decimal
    trend: str  # BULLISH, BEARISH, NEUTRAL
    rsi_value: float
    rsi_zone: str  # Overbought, Neutral, Oversold
    volatility_score: float
    momentum_score: float
    volume_trend: str  # Increasing, Decreasing, Stable
    signals: list[str] = Field(default_factory=list)


class OHLCVBarResponse(BaseModel):
    """Single OHLCV candlestick bar."""

    model_config = ConfigDict(from_attributes=True)

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime


class HeatmapEntry(BaseModel):
    """Heatmap entry for symbol visualization."""

    symbol: str
    price: Decimal
    change_percent_24h: Decimal
    volume_24h: Decimal
    market_cap_rank: Optional[int] = None


class ScreenerResponse(BaseModel):
    """Paginated screener results."""

    symbols: list[SymbolAnalysisResponse]
    total: int
    page: int
    page_size: int

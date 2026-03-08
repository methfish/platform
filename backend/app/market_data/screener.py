"""Market screener - analyzes symbols using technical indicators."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from app.market_data.indicators import rsi, macd, bollinger_bands


class TrendDirection(str, Enum):
    """Trend classification."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class SymbolAnalysis:
    """Analysis result for a single symbol."""

    symbol: str
    price: Decimal
    change_24h: Decimal
    volume_24h: Decimal
    trend: TrendDirection
    rsi_value: float
    rsi_zone: str  # Overbought, Neutral, Oversold
    volatility_score: float  # 0-100
    momentum_score: float  # 0-100
    volume_trend: str  # Increasing, Decreasing, Stable
    signals: list[str] = field(default_factory=list)


class ScreenerEngine:
    """Technical analysis screener for market data."""

    def __init__(self):
        self._rsi_period = 14
        self._macd_fast = 12
        self._macd_slow = 26
        self._bb_period = 20

    def analyze_symbol(
        self,
        symbol: str,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[float],
        price: Decimal,
        change_24h: Decimal,
        volume_24h: Decimal,
    ) -> SymbolAnalysis:
        """Analyze a single symbol using technical indicators."""
        signals = []

        # RSI Analysis
        rsi_vals = rsi(closes, self._rsi_period)
        rsi_value = rsi_vals[-1] if rsi_vals else 50.0
        if rsi_value > 70:
            rsi_zone = "Overbought"
            signals.append("RSI_OVERBOUGHT")
        elif rsi_value < 30:
            rsi_zone = "Oversold"
            signals.append("RSI_OVERSOLD")
        else:
            rsi_zone = "Neutral"

        # MACD Analysis
        macd_data = macd(closes, self._macd_fast, self._macd_slow)
        if macd_data["histogram"] and len(macd_data["histogram"]) > 0:
            last_hist = macd_data["histogram"][-1]
            if last_hist > 0:
                signals.append("MACD_BULLISH")
            else:
                signals.append("MACD_BEARISH")

        # Bollinger Bands Analysis
        bb_data = bollinger_bands(closes, self._bb_period, 2)
        volatility_score = self._calculate_volatility(closes, bb_data)

        # Trend Analysis
        trend = self._determine_trend(
            closes, rsi_value, macd_data, price, change_24h
        )

        # Momentum Score
        momentum_score = self._calculate_momentum(rsi_value, macd_data, closes)

        # Volume Trend
        volume_trend = self._analyze_volume_trend(volumes)

        return SymbolAnalysis(
            symbol=symbol,
            price=price,
            change_24h=change_24h,
            volume_24h=volume_24h,
            trend=trend,
            rsi_value=rsi_value,
            rsi_zone=rsi_zone,
            volatility_score=volatility_score,
            momentum_score=momentum_score,
            volume_trend=volume_trend,
            signals=signals,
        )

    def _determine_trend(
        self,
        closes: list[float],
        rsi_value: float,
        macd_data: dict,
        price: Decimal,
        change_24h: Decimal,
    ) -> TrendDirection:
        """Determine overall trend direction."""
        bullish_signals = 0
        bearish_signals = 0

        # Price trend
        if len(closes) >= 2:
            if closes[-1] > closes[-2]:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # RSI trend
        if rsi_value > 50:
            bullish_signals += 1
        elif rsi_value < 50:
            bearish_signals += 1

        # MACD trend
        if macd_data["histogram"] and len(macd_data["histogram"]) > 0:
            if macd_data["histogram"][-1] > 0:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # 24h change
        if change_24h > 0:
            bullish_signals += 1
        elif change_24h < 0:
            bearish_signals += 1

        if bullish_signals > bearish_signals:
            return TrendDirection.BULLISH
        elif bearish_signals > bullish_signals:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL

    def _calculate_volatility(
        self, closes: list[float], bb_data: dict
    ) -> float:
        """Calculate volatility score (0-100)."""
        if not closes or len(closes) < 2 or not bb_data.get("upper"):
            return 50.0

        upper = bb_data["upper"]
        lower = bb_data["lower"]
        if not upper or not lower:
            return 50.0

        bandwidth = upper[-1] - lower[-1]
        avg_price = closes[-1]
        if avg_price == 0:
            return 50.0

        volatility = (bandwidth / avg_price) * 100
        return min(100.0, volatility * 10)  # Scale to 0-100

    def _calculate_momentum(
        self, rsi_value: float, macd_data: dict, closes: list[float]
    ) -> float:
        """Calculate momentum score (0-100)."""
        momentum = 0.0

        # RSI component
        if rsi_value > 50:
            momentum += (rsi_value - 50) / 25  # 0-2 range
        else:
            momentum += (50 - rsi_value) / 25  # 0-2 range

        # MACD component
        if macd_data["histogram"] and len(macd_data["histogram"]) > 0:
            hist = macd_data["histogram"][-1]
            if hist > 0:
                momentum += 1.0
            else:
                momentum -= 1.0

        # Price momentum
        if len(closes) >= 5:
            recent_change = (closes[-1] - closes[-5]) / closes[-5]
            momentum += recent_change * 50

        return max(0.0, min(100.0, momentum * 10))

    def _analyze_volume_trend(self, volumes: list[float]) -> str:
        """Analyze volume trend."""
        if len(volumes) < 5:
            return "Stable"

        recent_avg = sum(volumes[-5:]) / 5
        older_avg = sum(volumes[-10:-5]) / 5 if len(volumes) >= 10 else recent_avg

        if older_avg == 0:
            return "Stable"

        change = (recent_avg - older_avg) / older_avg
        if change > 0.2:
            return "Increasing"
        elif change < -0.2:
            return "Decreasing"
        else:
            return "Stable"

    def screen_all(
        self, symbols_data: list[dict]
    ) -> list[SymbolAnalysis]:
        """Analyze multiple symbols."""
        analyses = []
        for data in symbols_data:
            analysis = self.analyze_symbol(
                symbol=data["symbol"],
                closes=data["closes"],
                highs=data["highs"],
                lows=data["lows"],
                volumes=data["volumes"],
                price=data["price"],
                change_24h=data["change_24h"],
                volume_24h=data["volume_24h"],
            )
            analyses.append(analysis)
        return analyses

    def filter_symbols(
        self,
        analyses: list[SymbolAnalysis],
        min_rsi: float | None = None,
        max_rsi: float | None = None,
        trend: TrendDirection | None = None,
        min_volume: Decimal | None = None,
        sort_by: str = "momentum_score",
    ) -> list[SymbolAnalysis]:
        """Filter and sort analysis results."""
        filtered = analyses

        if min_rsi is not None:
            filtered = [a for a in filtered if a.rsi_value >= min_rsi]

        if max_rsi is not None:
            filtered = [a for a in filtered if a.rsi_value <= max_rsi]

        if trend is not None:
            filtered = [a for a in filtered if a.trend == trend]

        if min_volume is not None:
            filtered = [a for a in filtered if a.volume_24h >= min_volume]

        # Sort
        if sort_by == "momentum_score":
            filtered.sort(key=lambda a: a.momentum_score, reverse=True)
        elif sort_by == "volatility_score":
            filtered.sort(key=lambda a: a.volatility_score, reverse=True)
        elif sort_by == "change_24h":
            filtered.sort(key=lambda a: a.change_24h, reverse=True)
        elif sort_by == "price":
            filtered.sort(key=lambda a: a.price, reverse=True)

        return filtered

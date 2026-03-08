"""
Market Regime Classification Skill - Shared between agents.

Classifies the current market regime based on price change, spread,
and volume patterns.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
)

logger = logging.getLogger(__name__)

# Regime constants.
REGIME_TRENDING_UP = "TRENDING_UP"
REGIME_TRENDING_DOWN = "TRENDING_DOWN"
REGIME_RANGING = "RANGING"
REGIME_HIGH_VOLATILITY = "HIGH_VOLATILITY"
REGIME_LOW_VOLATILITY = "LOW_VOLATILITY"

# Thresholds for classification.
_TREND_THRESHOLD_PCT = Decimal("1.0")      # |change| > 1 % -> trending
_HIGH_VOL_SPREAD_PCT = Decimal("0.5")      # spread > 0.5 % of mid -> high vol
_LOW_VOL_SPREAD_PCT = Decimal("0.05")      # spread < 0.05 % of mid -> low vol
_HIGH_VOLUME_MULTIPLE = Decimal("1.5")     # volume > 1.5x average -> activity spike


class MarketRegimeSkill(BaseSkill):
    """Deterministic market regime classifier."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "market_regime"

    @property
    def name(self) -> str:
        return "Market Regime Classification"

    @property
    def description(self) -> str:
        return (
            "Classifies market regime: TRENDING_UP, TRENDING_DOWN, RANGING, "
            "HIGH_VOLATILITY, LOW_VOLATILITY."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def required_inputs(self) -> list[str]:
        return ["market_data"]

    # --- Execution ---

    async def execute(self, ctx: SkillContext) -> SkillResult:
        md = ctx.market_data
        if not md:
            return self._failure("market_data is empty.")

        # Extract key indicators.
        price_change_pct = self._to_decimal(md.get("price_change_pct"))
        spread_pct = self._compute_spread_pct(ctx)
        volume_ratio = self._compute_volume_ratio(md)

        indicators: dict[str, Any] = {
            "price_change_pct": str(price_change_pct) if price_change_pct is not None else None,
            "spread_pct": str(spread_pct) if spread_pct is not None else None,
            "volume_ratio": str(volume_ratio) if volume_ratio is not None else None,
        }

        # Classification logic (priority order).
        regime, confidence = self._classify(
            price_change_pct, spread_pct, volume_ratio
        )

        return self._success(
            output={
                "regime": regime,
                "confidence": confidence,
                "indicators": indicators,
            },
            message=f"Market regime classified as {regime}.",
            confidence=confidence,
        )

    # --- Classification ---

    def _classify(
        self,
        price_change_pct: Decimal | None,
        spread_pct: Decimal | None,
        volume_ratio: Decimal | None,
    ) -> tuple[str, float]:
        """Return (regime, confidence) based on available indicators."""

        # High volatility takes priority if spread is wide.
        if spread_pct is not None and spread_pct > _HIGH_VOL_SPREAD_PCT:
            return REGIME_HIGH_VOLATILITY, 0.85

        # Trending detection based on price change.
        if price_change_pct is not None:
            if price_change_pct > _TREND_THRESHOLD_PCT:
                return REGIME_TRENDING_UP, 0.80
            if price_change_pct < -_TREND_THRESHOLD_PCT:
                return REGIME_TRENDING_DOWN, 0.80

        # Low volatility if spread is very tight.
        if spread_pct is not None and spread_pct < _LOW_VOL_SPREAD_PCT:
            return REGIME_LOW_VOLATILITY, 0.75

        # Default: ranging.
        return REGIME_RANGING, 0.60

    # --- Helpers ---

    def _compute_spread_pct(self, ctx: SkillContext) -> Decimal | None:
        """Compute spread as a percentage of mid price."""
        bid = ctx.bid_price
        ask = ctx.ask_price
        if bid is None or ask is None or bid <= 0:
            # Try from market_data dict.
            bid = self._to_decimal(ctx.market_data.get("bid"))
            ask = self._to_decimal(ctx.market_data.get("ask"))
            if bid is None or ask is None or bid <= 0:
                return None

        mid = (bid + ask) / Decimal("2")
        if mid <= 0:
            return None
        return ((ask - bid) / mid) * Decimal("100")

    @staticmethod
    def _compute_volume_ratio(md: dict[str, Any]) -> Decimal | None:
        """Compute current volume as a ratio of average volume."""
        current = md.get("volume_24h") or md.get("volume")
        average = md.get("avg_volume") or md.get("average_volume")
        if current is None or average is None:
            return None
        try:
            current_dec = Decimal(str(current))
            average_dec = Decimal(str(average))
            if average_dec <= 0:
                return None
            return current_dec / average_dec
        except (ArithmeticError, ValueError):
            return None

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Safely convert a value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError):
            return None

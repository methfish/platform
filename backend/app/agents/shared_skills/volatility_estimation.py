"""
Volatility Estimation Skill - Shared between agents.

Estimates volatility from available market data using spread-based
or price-range-based methods.
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

# Method constants.
METHOD_SPREAD = "spread_based"
METHOD_RANGE = "price_range"
METHOD_CHANGE = "price_change"
METHOD_FALLBACK = "fallback_default"

# Default fallback volatility (used when no data is available).
_DEFAULT_VOLATILITY = Decimal("0.02")  # 2 %


class VolatilityEstimationSkill(BaseSkill):
    """Deterministic volatility estimator using simplified methods."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "volatility_estimation"

    @property
    def name(self) -> str:
        return "Volatility Estimation"

    @property
    def description(self) -> str:
        return (
            "Estimates volatility from available data using spread-based "
            "or price-range-based methods."
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

        # Try methods in order of preference.
        estimate, method = self._try_spread_method(ctx)
        if estimate is None:
            estimate, method = self._try_range_method(md)
        if estimate is None:
            estimate, method = self._try_change_method(md)
        if estimate is None:
            estimate = _DEFAULT_VOLATILITY
            method = METHOD_FALLBACK

        # Determine time horizon from available data.
        time_horizon = md.get("time_horizon", "24h")

        confidence = self._confidence_for_method(method)

        return self._success(
            output={
                "volatility_estimate": str(estimate),
                "method": method,
                "time_horizon": str(time_horizon),
            },
            message=f"Volatility estimated at {estimate} using {method}.",
            confidence=confidence,
        )

    # --- Estimation methods ---

    def _try_spread_method(
        self, ctx: SkillContext
    ) -> tuple[Decimal | None, str]:
        """
        Estimate volatility from bid-ask spread.

        Spread is a proxy for near-term volatility and liquidity.
        Multiply by a scaling factor to approximate annualised-like vol.
        """
        bid = ctx.bid_price
        ask = ctx.ask_price
        if bid is None or ask is None:
            bid = self._to_decimal(ctx.market_data.get("bid"))
            ask = self._to_decimal(ctx.market_data.get("ask"))
        if bid is None or ask is None or bid <= 0:
            return None, ""

        mid = (bid + ask) / Decimal("2")
        if mid <= 0:
            return None, ""

        spread_pct = (ask - bid) / mid
        # Scale spread to approximate short-term volatility.
        # Empirically, spread * 10 is a rough proxy for daily vol in crypto.
        vol_estimate = spread_pct * Decimal("10")
        return vol_estimate, METHOD_SPREAD

    @staticmethod
    def _try_range_method(
        md: dict[str, Any],
    ) -> tuple[Decimal | None, str]:
        """Estimate volatility from high-low range."""
        high = md.get("high") or md.get("high_24h")
        low = md.get("low") or md.get("low_24h")
        if high is None or low is None:
            return None, ""
        try:
            high_dec = Decimal(str(high))
            low_dec = Decimal(str(low))
            if low_dec <= 0:
                return None, ""
            range_pct = (high_dec - low_dec) / low_dec
            return range_pct, METHOD_RANGE
        except (ArithmeticError, ValueError):
            return None, ""

    @staticmethod
    def _try_change_method(
        md: dict[str, Any],
    ) -> tuple[Decimal | None, str]:
        """Estimate volatility from absolute price change percentage."""
        change = md.get("price_change_pct")
        if change is None:
            return None, ""
        try:
            change_dec = abs(Decimal(str(change))) / Decimal("100")
            return change_dec, METHOD_CHANGE
        except (ArithmeticError, ValueError):
            return None, ""

    @staticmethod
    def _confidence_for_method(method: str) -> float:
        """Return confidence level based on estimation method."""
        return {
            METHOD_SPREAD: 0.70,
            METHOD_RANGE: 0.75,
            METHOD_CHANGE: 0.55,
            METHOD_FALLBACK: 0.20,
        }.get(method, 0.20)

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError):
            return None

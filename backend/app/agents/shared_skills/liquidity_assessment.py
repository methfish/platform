"""
Liquidity Assessment Skill - Shared between agents.

Assesses market liquidity based on spread, volume, and order-book
depth (when available). Produces a 0-100 liquidity score.
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

# Classification thresholds.
_HIGH_THRESHOLD = 70
_MEDIUM_THRESHOLD = 40

# Spread scoring: tight spread -> high score.
_SPREAD_EXCELLENT = Decimal("0.02")   # < 0.02 % -> 100 pts
_SPREAD_GOOD = Decimal("0.10")        # < 0.10 % -> 75 pts
_SPREAD_FAIR = Decimal("0.50")        # < 0.50 % -> 50 pts
_SPREAD_POOR = Decimal("1.00")        # < 1.00 % -> 25 pts

# Volume scoring: relative to average.
_VOL_HIGH_RATIO = Decimal("1.5")
_VOL_NORMAL_RATIO = Decimal("0.8")
_VOL_LOW_RATIO = Decimal("0.3")


class LiquidityAssessmentSkill(BaseSkill):
    """Deterministic liquidity scorer."""

    # --- Abstract property implementations ---

    @property
    def skill_id(self) -> str:
        return "liquidity_assessment"

    @property
    def name(self) -> str:
        return "Liquidity Assessment"

    @property
    def description(self) -> str:
        return (
            "Assesses liquidity based on spread, volume, and order book "
            "depth. Outputs a 0-100 score and classification."
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

        factors: dict[str, Any] = {}
        component_scores: list[float] = []

        # Factor 1: Spread score.
        spread_score = self._score_spread(ctx, md)
        if spread_score is not None:
            factors["spread_score"] = spread_score
            component_scores.append(spread_score)

        # Factor 2: Volume score.
        volume_score = self._score_volume(md)
        if volume_score is not None:
            factors["volume_score"] = volume_score
            component_scores.append(volume_score)

        # Factor 3: Order book depth score.
        depth_score = self._score_depth(md)
        if depth_score is not None:
            factors["depth_score"] = depth_score
            component_scores.append(depth_score)

        if not component_scores:
            return self._failure(
                "Insufficient data to assess liquidity "
                "(no spread, volume, or depth available)."
            )

        # Aggregate: simple average of available components.
        liquidity_score = round(
            sum(component_scores) / len(component_scores)
        )
        liquidity_score = max(0, min(100, liquidity_score))

        if liquidity_score >= _HIGH_THRESHOLD:
            classification = "HIGH"
        elif liquidity_score >= _MEDIUM_THRESHOLD:
            classification = "MEDIUM"
        else:
            classification = "LOW"

        confidence = 0.60 + (len(component_scores) * 0.10)
        confidence = min(confidence, 0.95)

        return self._success(
            output={
                "liquidity_score": liquidity_score,
                "classification": classification,
                "factors": factors,
            },
            message=(
                f"Liquidity score: {liquidity_score}/100 ({classification})."
            ),
            confidence=confidence,
        )

    # --- Component scorers ---

    def _score_spread(
        self, ctx: SkillContext, md: dict[str, Any]
    ) -> float | None:
        """Score based on bid-ask spread percentage."""
        bid = ctx.bid_price
        ask = ctx.ask_price
        if bid is None or ask is None:
            bid = self._to_decimal(md.get("bid"))
            ask = self._to_decimal(md.get("ask"))
        if bid is None or ask is None or bid <= 0:
            return None

        mid = (bid + ask) / Decimal("2")
        if mid <= 0:
            return None

        spread_pct = ((ask - bid) / mid) * Decimal("100")

        if spread_pct < _SPREAD_EXCELLENT:
            return 100.0
        if spread_pct < _SPREAD_GOOD:
            return 75.0
        if spread_pct < _SPREAD_FAIR:
            return 50.0
        if spread_pct < _SPREAD_POOR:
            return 25.0
        return 10.0

    @staticmethod
    def _score_volume(md: dict[str, Any]) -> float | None:
        """Score based on volume relative to average."""
        current = md.get("volume_24h") or md.get("volume")
        average = md.get("avg_volume") or md.get("average_volume")
        if current is None or average is None:
            # If only absolute volume is available, score coarsely.
            if current is not None:
                try:
                    vol = Decimal(str(current))
                    if vol > 0:
                        return 50.0  # We have volume but no baseline.
                except (ArithmeticError, ValueError):
                    pass
            return None

        try:
            current_dec = Decimal(str(current))
            average_dec = Decimal(str(average))
            if average_dec <= 0:
                return None

            ratio = current_dec / average_dec

            if ratio >= _VOL_HIGH_RATIO:
                return 90.0
            if ratio >= _VOL_NORMAL_RATIO:
                return 65.0
            if ratio >= _VOL_LOW_RATIO:
                return 35.0
            return 15.0
        except (ArithmeticError, ValueError):
            return None

    @staticmethod
    def _score_depth(md: dict[str, Any]) -> float | None:
        """Score based on order book depth if available."""
        depth = md.get("order_book_depth") or md.get("depth")
        if depth is None:
            return None

        # Depth can be reported as a number of levels or total value.
        try:
            depth_val = float(depth)
            if depth_val <= 0:
                return 10.0
            # Normalise depth to a 0-100 score (heuristic).
            # Assume 100 levels or 100k value -> max score.
            score = min(100.0, depth_val / 100.0 * 100.0)
            return max(10.0, score)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError):
            return None

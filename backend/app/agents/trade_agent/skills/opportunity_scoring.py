"""
Opportunity Scoring skill.

Scores each symbol 0-100 based on spread tightness, volume, and
price momentum (when available). Returns ranked candidates and a
no_trade flag when the best score is below the minimum threshold.

HYBRID execution type - deterministic scoring with the option to
augment scores via model-based momentum signals.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)

# Minimum score required to consider a symbol tradeable.
_MIN_SCORE_THRESHOLD = 30

# Component weights (must sum to 100).
_WEIGHT_SPREAD = 40
_WEIGHT_VOLUME = 35
_WEIGHT_MOMENTUM = 25


class OpportunityScoringSkill(BaseSkill):
    """Score and rank symbols by trade opportunity quality."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "opportunity_scoring"

    @property
    def name(self) -> str:
        return "Opportunity Scoring"

    @property
    def description(self) -> str:
        return (
            "Scores each symbol 0-100 based on spread tightness, "
            "volume, and price momentum. Returns ranked candidates."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.HYBRID

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    @property
    def prerequisites(self) -> list[str]:
        return ["market_context"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        market_result = ctx.upstream_results["market_context"]
        symbol_contexts: list[dict] = market_result.output.get("symbol_contexts", [])

        if not symbol_contexts:
            return self._failure("No symbol contexts available from market_context.")

        ranked: list[dict] = []

        for sc in symbol_contexts:
            spread_score = self._score_spread(sc)
            volume_score = self._score_volume(sc)
            momentum_score = self._score_momentum(sc, ctx)

            total = (
                spread_score * _WEIGHT_SPREAD
                + volume_score * _WEIGHT_VOLUME
                + momentum_score * _WEIGHT_MOMENTUM
            ) / 100

            ranked.append({
                "symbol": sc["symbol"],
                "score": round(total, 2),
                "spread_score": round(spread_score, 2),
                "volume_score": round(volume_score, 2),
                "momentum_score": round(momentum_score, 2),
                "low_liquidity": sc.get("low_liquidity", False),
            })

        # Sort descending by score.
        ranked.sort(key=lambda c: c["score"], reverse=True)

        best_score = ranked[0]["score"] if ranked else 0
        no_trade = best_score < _MIN_SCORE_THRESHOLD

        return self._success(
            output={
                "ranked_candidates": ranked,
                "no_trade": no_trade,
                "best_score": best_score,
                "threshold": _MIN_SCORE_THRESHOLD,
            },
            message=(
                f"Best opportunity: {ranked[0]['symbol']} "
                f"(score={best_score}). "
                f"{'No trade - below threshold.' if no_trade else 'Candidates available.'}"
            )
            if ranked
            else "No candidates to score.",
            confidence=min(best_score / 100, 1.0) if ranked else 0.0,
        )

    # ------------------------------------------------------------------
    # Component scorers (0-100 each)
    # ------------------------------------------------------------------

    @staticmethod
    def _score_spread(sc: dict) -> float:
        """Tighter spread -> higher score."""
        spread_class = sc.get("spread_class", "wide")
        if spread_class == "tight":
            return 100.0
        if spread_class == "moderate":
            return 60.0
        return 20.0

    @staticmethod
    def _score_volume(sc: dict) -> float:
        """Higher volume -> higher score, with diminishing returns."""
        vol = Decimal(sc.get("volume_24h", "0"))
        if vol <= 0:
            return 0.0
        # Scale: 50k -> ~50, 500k -> ~85, 5M -> ~100
        import math

        raw = math.log10(float(vol) + 1) * 15
        return min(raw, 100.0)

    @staticmethod
    def _score_momentum(sc: dict, ctx: SkillContext) -> float:
        """
        Price momentum score.

        Reads momentum data from market_data if available, otherwise
        returns a neutral 50.
        """
        symbol = sc["symbol"]
        md = ctx.market_data.get(symbol, {})

        # Expect a 'momentum' key in [-1, 1] range.
        momentum = md.get("momentum")
        if momentum is None:
            return 50.0

        # Map [-1, 1] to [0, 100].
        clamped = max(-1.0, min(1.0, float(momentum)))
        return (clamped + 1.0) * 50.0

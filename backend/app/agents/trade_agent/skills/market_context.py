"""
Market Context skill.

Processes raw market data for each symbol in the context and
produces a normalized summary: last price, bid/ask spread
classification, 24-h volume, and liquidity flags.

Deterministic - pure computation on existing market data.
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

# Spread classification thresholds (as fraction of mid-price).
_TIGHT_THRESHOLD = Decimal("0.001")    # 0.1%
_MODERATE_THRESHOLD = Decimal("0.005")  # 0.5%

# Minimum 24-h volume to consider liquid (in quote currency).
_MIN_LIQUID_VOLUME = Decimal("50000")


class MarketContextSkill(BaseSkill):
    """Normalize market data for each symbol into a structured summary."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "market_context"

    @property
    def name(self) -> str:
        return "Market Context"

    @property
    def description(self) -> str:
        return (
            "Processes market data for each symbol: last price, "
            "bid/ask spread classification, 24-h volume, and "
            "liquidity flags."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols", "market_data"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        symbol_contexts: list[dict] = []

        for symbol in ctx.symbols:
            md = ctx.market_data.get(symbol, {})

            last_price = Decimal(str(md.get("last_price", "0")))
            bid = Decimal(str(md.get("bid_price", "0")))
            ask = Decimal(str(md.get("ask_price", "0")))
            volume_24h = Decimal(str(md.get("volume_24h", "0")))

            # Compute spread metrics.
            mid = (bid + ask) / Decimal("2") if (bid > 0 and ask > 0) else last_price
            spread_abs = ask - bid if (bid > 0 and ask > 0) else Decimal("0")
            spread_pct = (
                (spread_abs / mid) if mid > 0 else Decimal("0")
            )

            # Classify spread.
            if spread_pct <= _TIGHT_THRESHOLD:
                spread_class = "tight"
            elif spread_pct <= _MODERATE_THRESHOLD:
                spread_class = "moderate"
            else:
                spread_class = "wide"

            # Flag low liquidity.
            low_liquidity = volume_24h < _MIN_LIQUID_VOLUME

            symbol_contexts.append({
                "symbol": symbol,
                "last_price": str(last_price),
                "bid_price": str(bid),
                "ask_price": str(ask),
                "mid_price": str(mid),
                "spread_abs": str(spread_abs),
                "spread_pct": str(spread_pct),
                "spread_class": spread_class,
                "volume_24h": str(volume_24h),
                "low_liquidity": low_liquidity,
            })

        return self._success(
            output={
                "symbol_contexts": symbol_contexts,
                "num_symbols": len(symbol_contexts),
            },
            message=f"Market context computed for {len(symbol_contexts)} symbols.",
        )

"""
Unit tests for the 6 shared agent skills.

Each skill receives a SkillContext and returns a SkillResult.
Tests cover SUCCESS, FAILURE, and SKIPPED outcomes.
"""

import pytest
from decimal import Decimal

from app.agents.types import (
    SkillContext,
    SkillResult,
    SkillStatus,
)
from app.agents.shared_skills.market_regime import MarketRegimeSkill
from app.agents.shared_skills.volatility_estimation import VolatilityEstimationSkill
from app.agents.shared_skills.liquidity_assessment import LiquidityAssessmentSkill
from app.agents.shared_skills.exchange_health import ExchangeHealthSkill
from app.agents.shared_skills.confidence_calibration import ConfidenceCalibrationSkill
from app.agents.shared_skills.alert_generation import AlertGenerationSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    *,
    market_data: dict | None = None,
    risk_state: dict | None = None,
    bid_price: Decimal | None = None,
    ask_price: Decimal | None = None,
    upstream_results: dict[str, SkillResult] | None = None,
) -> SkillContext:
    """Build a SkillContext with sensible defaults for shared-skill tests."""
    return SkillContext(
        symbol="BTCUSDT",
        market_data=market_data or {},
        risk_state=risk_state or {},
        bid_price=bid_price,
        ask_price=ask_price,
        upstream_results=upstream_results or {},
    )


def _make_upstream(
    skill_id: str,
    output: dict,
    *,
    status: SkillStatus = SkillStatus.SUCCESS,
    confidence: float | None = 0.85,
    message: str = "",
    requires_human_review: bool = False,
) -> SkillResult:
    """Shorthand for building an upstream SkillResult."""
    return SkillResult(
        skill_id=skill_id,
        status=status,
        output=output,
        message=message,
        confidence=confidence,
        requires_human_review=requires_human_review,
    )


# ===========================================================================
# MarketRegimeSkill
# ===========================================================================


class TestMarketRegimeSkill:
    """Tests for the market regime classification skill."""

    @pytest.mark.asyncio
    async def test_trending_up_positive_change(self):
        """Positive price change > 1 % -> TRENDING_UP."""
        ctx = _make_context(
            market_data={"price_change_pct": "2.5"},
            bid_price=Decimal("49999"),
            ask_price=Decimal("50001"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "TRENDING_UP"
        assert result.output["confidence"] > 0

    @pytest.mark.asyncio
    async def test_trending_down_negative_change(self):
        """Negative price change < -1 % -> TRENDING_DOWN."""
        ctx = _make_context(
            market_data={"price_change_pct": "-3.0"},
            bid_price=Decimal("49999"),
            ask_price=Decimal("50001"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "TRENDING_DOWN"

    @pytest.mark.asyncio
    async def test_ranging_small_change(self):
        """Small price change within +/-1 % and normal spread -> RANGING."""
        ctx = _make_context(
            market_data={"price_change_pct": "0.3"},
            bid_price=Decimal("49990"),
            ask_price=Decimal("50010"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "RANGING"

    @pytest.mark.asyncio
    async def test_high_volatility_wide_spread(self):
        """Spread > 0.5 % of mid -> HIGH_VOLATILITY (takes priority)."""
        # spread ~1% of mid
        ctx = _make_context(
            market_data={"price_change_pct": "0.5"},
            bid_price=Decimal("49500"),
            ask_price=Decimal("50500"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "HIGH_VOLATILITY"

    @pytest.mark.asyncio
    async def test_low_volatility_tight_spread(self):
        """Spread < 0.05 % and small price change -> LOW_VOLATILITY."""
        # Spread of ~0.002% (extremely tight)
        ctx = _make_context(
            market_data={"price_change_pct": "0.1"},
            bid_price=Decimal("49999.5"),
            ask_price=Decimal("50000.5"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "LOW_VOLATILITY"

    @pytest.mark.asyncio
    async def test_empty_market_data_fails(self):
        """Empty market_data -> FAILURE."""
        ctx = _make_context(market_data={})
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.FAILURE

    @pytest.mark.asyncio
    async def test_indicators_in_output(self):
        """Output should include indicators dict."""
        ctx = _make_context(
            market_data={"price_change_pct": "1.5"},
            bid_price=Decimal("49999"),
            ask_price=Decimal("50001"),
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert "indicators" in result.output
        assert "price_change_pct" in result.output["indicators"]

    @pytest.mark.asyncio
    async def test_bid_ask_from_market_data_dict(self):
        """When bid/ask not on context, falls back to market_data dict."""
        ctx = _make_context(
            market_data={
                "price_change_pct": "2.0",
                "bid": "49999",
                "ask": "50001",
            },
        )
        skill = MarketRegimeSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["regime"] == "TRENDING_UP"

    @pytest.mark.asyncio
    async def test_skill_metadata(self):
        """Verify skill metadata properties."""
        skill = MarketRegimeSkill()
        assert skill.skill_id == "market_regime"
        assert "market_data" in skill.required_inputs


# ===========================================================================
# VolatilityEstimationSkill
# ===========================================================================


class TestVolatilityEstimationSkill:
    """Tests for the volatility estimation skill."""

    @pytest.mark.asyncio
    async def test_spread_based_estimation(self):
        """Bid/ask present -> spread-based method."""
        ctx = _make_context(
            market_data={"some_key": "value"},
            bid_price=Decimal("49900"),
            ask_price=Decimal("50100"),
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["method"] == "spread_based"
        vol = Decimal(result.output["volatility_estimate"])
        assert vol > 0

    @pytest.mark.asyncio
    async def test_range_based_estimation(self):
        """High/low present, no bid/ask -> price-range method."""
        ctx = _make_context(
            market_data={"high": "51000", "low": "49000"},
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["method"] == "price_range"

    @pytest.mark.asyncio
    async def test_change_based_estimation(self):
        """Only price_change_pct available -> price-change method."""
        ctx = _make_context(
            market_data={"price_change_pct": "3.5"},
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["method"] == "price_change"

    @pytest.mark.asyncio
    async def test_fallback_on_missing_data(self):
        """No useful data -> fallback 2 % default."""
        ctx = _make_context(
            market_data={"irrelevant_key": "value"},
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["method"] == "fallback_default"
        vol = Decimal(result.output["volatility_estimate"])
        assert vol == Decimal("0.02")

    @pytest.mark.asyncio
    async def test_empty_market_data_fails(self):
        """Empty market_data -> FAILURE."""
        ctx = _make_context(market_data={})
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.FAILURE

    @pytest.mark.asyncio
    async def test_time_horizon_in_output(self):
        """Output should include time_horizon."""
        ctx = _make_context(
            market_data={"price_change_pct": "1.0", "time_horizon": "1h"},
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["time_horizon"] == "1h"

    @pytest.mark.asyncio
    async def test_confidence_varies_by_method(self):
        """Spread-based should have higher confidence than fallback."""
        # Spread-based
        ctx_spread = _make_context(
            market_data={"some_key": "value"},
            bid_price=Decimal("49900"),
            ask_price=Decimal("50100"),
        )
        skill = VolatilityEstimationSkill()
        result_spread = await skill.execute(ctx_spread)

        # Fallback
        ctx_fallback = _make_context(
            market_data={"irrelevant_key": "value"},
        )
        result_fallback = await skill.execute(ctx_fallback)

        assert result_spread.confidence > result_fallback.confidence

    @pytest.mark.asyncio
    async def test_bid_ask_from_market_data_dict(self):
        """When bid/ask not on context, falls back to market_data dict."""
        ctx = _make_context(
            market_data={"bid": "49900", "ask": "50100"},
        )
        skill = VolatilityEstimationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["method"] == "spread_based"


# ===========================================================================
# LiquidityAssessmentSkill
# ===========================================================================


class TestLiquidityAssessmentSkill:
    """Tests for the liquidity assessment skill."""

    @pytest.mark.asyncio
    async def test_high_liquidity(self):
        """Tight spread + high volume -> HIGH classification, score >= 70."""
        ctx = _make_context(
            market_data={
                "volume_24h": "150000",
                "avg_volume": "100000",
            },
            bid_price=Decimal("49999"),
            ask_price=Decimal("50001"),
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["classification"] == "HIGH"
        assert result.output["liquidity_score"] >= 70

    @pytest.mark.asyncio
    async def test_low_liquidity(self):
        """Wide spread + low volume -> LOW classification, score < 40."""
        ctx = _make_context(
            market_data={
                "volume_24h": "1000",
                "avg_volume": "100000",
            },
            bid_price=Decimal("49000"),
            ask_price=Decimal("51000"),
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["classification"] == "LOW"
        assert result.output["liquidity_score"] < 40

    @pytest.mark.asyncio
    async def test_medium_liquidity(self):
        """Moderate conditions -> MEDIUM classification."""
        ctx = _make_context(
            market_data={
                "volume_24h": "80000",
                "avg_volume": "100000",
            },
            bid_price=Decimal("49850"),
            ask_price=Decimal("50150"),
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["classification"] in ("MEDIUM", "HIGH")
        assert 0 <= result.output["liquidity_score"] <= 100

    @pytest.mark.asyncio
    async def test_empty_market_data_fails(self):
        """Empty market_data -> FAILURE."""
        ctx = _make_context(market_data={})
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.FAILURE

    @pytest.mark.asyncio
    async def test_no_spread_volume_depth_fails(self):
        """No spread, volume, or depth data available -> FAILURE."""
        ctx = _make_context(
            market_data={"irrelevant": "data"},
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.FAILURE

    @pytest.mark.asyncio
    async def test_factors_in_output(self):
        """Output should include individual factor scores."""
        ctx = _make_context(
            market_data={
                "volume_24h": "120000",
                "avg_volume": "100000",
                "order_book_depth": "50",
            },
            bid_price=Decimal("49999"),
            ask_price=Decimal("50001"),
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        factors = result.output["factors"]
        assert "spread_score" in factors
        assert "volume_score" in factors
        assert "depth_score" in factors

    @pytest.mark.asyncio
    async def test_score_clamped_0_to_100(self):
        """Liquidity score should always be in [0, 100]."""
        ctx = _make_context(
            market_data={"volume_24h": "500000", "avg_volume": "100000"},
            bid_price=Decimal("49999.5"),
            ask_price=Decimal("50000.5"),
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert 0 <= result.output["liquidity_score"] <= 100

    @pytest.mark.asyncio
    async def test_volume_only_partial_score(self):
        """Volume present but no average -> 50 pts partial score."""
        ctx = _make_context(
            market_data={"volume_24h": "50000"},
        )
        skill = LiquidityAssessmentSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["factors"].get("volume_score") == 50.0


# ===========================================================================
# ExchangeHealthSkill
# ===========================================================================


class TestExchangeHealthSkill:
    """Tests for the exchange health check skill."""

    @pytest.mark.asyncio
    async def test_healthy_exchange(self):
        """Status OK with low latency -> HEALTHY, is_healthy True."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {
                    "status": "OK",
                    "latency_ms": 100,
                }
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "HEALTHY"
        assert result.output["is_healthy"] is True
        assert result.output["latency_ms"] == 100

    @pytest.mark.asyncio
    async def test_degraded_exchange(self):
        """Status DEGRADED -> DEGRADED, is_healthy False."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {
                    "status": "DEGRADED",
                    "latency_ms": 1500,
                    "degraded_services": ["order_book", "websocket"],
                }
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "DEGRADED"
        assert result.output["is_healthy"] is False
        assert result.output["degraded_services"] == ["order_book", "websocket"]

    @pytest.mark.asyncio
    async def test_down_exchange(self):
        """Status DOWN -> DOWN, is_healthy False."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {"status": "DOWN"},
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "DOWN"
        assert result.output["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_missing_status_unknown(self):
        """No exchange health data in risk_state -> UNKNOWN, is_healthy False."""
        ctx = _make_context(
            risk_state={"some_other_key": "value"},
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "UNKNOWN"
        assert result.output["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_empty_risk_state_fails(self):
        """Empty risk_state -> FAILURE."""
        ctx = _make_context(risk_state={})
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.FAILURE

    @pytest.mark.asyncio
    async def test_slow_exchange(self):
        """Latency > 500ms but < 2000ms and healthy status -> SLOW, is_healthy True."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {
                    "status": "CONNECTED",
                    "latency_ms": 800,
                }
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "SLOW"
        assert result.output["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_high_latency_degrades(self):
        """Latency > 2000ms even with OK status -> DEGRADED."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {
                    "status": "OK",
                    "latency_ms": 3000,
                }
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "DEGRADED"
        assert result.output["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_string_exchange_status(self):
        """risk_state with exchange_status as a plain string."""
        ctx = _make_context(
            risk_state={"exchange_status": "HEALTHY"},
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "HEALTHY"
        assert result.output["is_healthy"] is True

    @pytest.mark.asyncio
    async def test_degraded_services_trigger_degraded(self):
        """Degraded services present even with OK status -> DEGRADED."""
        ctx = _make_context(
            risk_state={
                "exchange_health": {
                    "status": "OK",
                    "latency_ms": 200,
                    "degraded_services": ["websocket"],
                }
            }
        )
        skill = ExchangeHealthSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["exchange_status"] == "DEGRADED"
        assert result.output["is_healthy"] is False

    @pytest.mark.asyncio
    async def test_skill_metadata(self):
        """Verify skill metadata properties."""
        skill = ExchangeHealthSkill()
        assert skill.skill_id == "exchange_health"
        assert "risk_state" in skill.required_inputs


# ===========================================================================
# ConfidenceCalibrationSkill
# ===========================================================================


class TestConfidenceCalibrationSkill:
    """Tests for the confidence calibration skill."""

    @pytest.mark.asyncio
    async def test_high_confidence_upstream(self):
        """All upstream skills with high confidence -> high calibrated score."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.90),
            "skill_b": _make_upstream("skill_b", {"data": 2}, confidence=0.85),
            "skill_c": _make_upstream("skill_c", {"data": 3}, confidence=0.80),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["calibrated_confidence"] >= 0.80
        assert len(result.output["contributing_skills"]) == 3
        assert result.output["adjustment_factors"]["failed_skill_count"] == 0

    @pytest.mark.asyncio
    async def test_low_confidence_upstream(self):
        """All upstream skills with low confidence -> lower calibrated score."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.30),
            "skill_b": _make_upstream("skill_b", {"data": 2}, confidence=0.25),
            "skill_c": _make_upstream("skill_c", {"data": 3}, confidence=0.20),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        # All are below 0.5 threshold -> penalty applied + low average.
        assert result.output["calibrated_confidence"] < 0.50
        assert result.output["adjustment_factors"]["low_confidence_skill_count"] == 3

    @pytest.mark.asyncio
    async def test_failed_skills_penalty(self):
        """Failed upstream skills -> penalty reduces calibrated confidence."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.90),
            "skill_b": _make_upstream(
                "skill_b", {}, status=SkillStatus.FAILURE, confidence=None,
                message="something failed",
            ),
            "skill_c": _make_upstream(
                "skill_c", {}, status=SkillStatus.ERROR, confidence=None,
                message="error occurred",
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["adjustment_factors"]["failed_skill_count"] == 2
        # The failure penalty should lower the calibrated confidence.
        assert result.output["calibrated_confidence"] < 0.90

    @pytest.mark.asyncio
    async def test_no_upstream_results_default(self):
        """No upstream results -> default 0.50 confidence."""
        ctx = _make_context(upstream_results={})

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["calibrated_confidence"] == 0.50
        assert result.output["contributing_skills"] == []

    @pytest.mark.asyncio
    async def test_confidence_clamped(self):
        """Calibrated confidence should be between MIN and MAX bounds."""
        # Extreme failure scenario.
        upstream = {
            f"skill_{i}": _make_upstream(
                f"skill_{i}", {}, status=SkillStatus.FAILURE,
                confidence=None, message="fail",
            )
            for i in range(10)
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert 0.05 <= result.output["calibrated_confidence"] <= 0.99

    @pytest.mark.asyncio
    async def test_skips_self_in_upstream(self):
        """Skill should skip its own entry in upstream_results."""
        upstream = {
            "confidence_calibration": _make_upstream(
                "confidence_calibration", {"old": True}, confidence=0.50,
            ),
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.80),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        contributing_ids = [s["skill_id"] for s in result.output["contributing_skills"]]
        assert "confidence_calibration" not in contributing_ids

    @pytest.mark.asyncio
    async def test_mixed_confidence_values(self):
        """Mix of high and low confidence -> average reflects both."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {}, confidence=0.95),
            "skill_b": _make_upstream("skill_b", {}, confidence=0.30),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = ConfidenceCalibrationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        # Average of 0.95 and 0.30 is ~0.625, one low confidence skill out of 2
        # (ratio 0.5 is not > 0.5, so no extra penalty).
        cal = result.output["calibrated_confidence"]
        assert 0.50 <= cal <= 0.80


# ===========================================================================
# AlertGenerationSkill
# ===========================================================================


class TestAlertGenerationSkill:
    """Tests for the alert generation skill."""

    @pytest.mark.asyncio
    async def test_no_alerts_on_clean_results(self):
        """All upstream SUCCESS with high confidence -> no alerts (or info-only)."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.90),
            "skill_b": _make_upstream("skill_b", {"data": 2}, confidence=0.85),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        # No critical/high/medium alerts expected.
        severe_alerts = [
            a for a in result.output["alerts"]
            if a["severity"] in ("critical", "high", "medium")
        ]
        assert len(severe_alerts) == 0

    @pytest.mark.asyncio
    async def test_alerts_on_failures(self):
        """Failed and errored upstream skills -> high/critical alerts."""
        upstream = {
            "skill_a": _make_upstream(
                "skill_a", {}, status=SkillStatus.ERROR,
                confidence=None, message="unexpected error",
            ),
            "skill_b": _make_upstream(
                "skill_b", {}, status=SkillStatus.FAILURE,
                confidence=None, message="data missing",
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        severities = [a["severity"] for a in result.output["alerts"]]
        assert "critical" in severities  # ERROR -> critical
        assert "high" in severities       # FAILURE -> high
        assert result.output["alert_count"] >= 2

    @pytest.mark.asyncio
    async def test_alerts_on_timeout(self):
        """Timed-out upstream skill -> high severity alert."""
        upstream = {
            "skill_a": _make_upstream(
                "skill_a", {}, status=SkillStatus.TIMEOUT,
                confidence=None, message="skill timed out",
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        severities = [a["severity"] for a in result.output["alerts"]]
        assert "high" in severities

    @pytest.mark.asyncio
    async def test_alerts_on_low_confidence(self):
        """Successful skill with confidence < 0.4 -> medium alert."""
        upstream = {
            "skill_a": _make_upstream("skill_a", {"data": 1}, confidence=0.25),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        medium_alerts = [
            a for a in result.output["alerts"]
            if a["severity"] == "medium"
        ]
        assert len(medium_alerts) >= 1

    @pytest.mark.asyncio
    async def test_human_review_info_alert(self):
        """Skill requiring human review -> info alert."""
        upstream = {
            "skill_a": _make_upstream(
                "skill_a", {"data": 1}, confidence=0.80,
                requires_human_review=True,
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        info_alerts = [
            a for a in result.output["alerts"]
            if a["severity"] == "info"
        ]
        assert len(info_alerts) >= 1

    @pytest.mark.asyncio
    async def test_incident_detection_high_priority_alert(self):
        """Incident detection output with high-priority incidents -> high alert."""
        upstream = {
            "incident_detection": _make_upstream(
                "incident_detection",
                {
                    "incidents": [
                        {"type": "large_loss", "priority_score": 0.9, "order_id": "x"},
                    ],
                    "total_count": 1,
                },
                confidence=0.90,
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        high_alerts = [
            a for a in result.output["alerts"]
            if a["severity"] == "high" and a["source_skill"] == "incident_detection"
        ]
        assert len(high_alerts) >= 1

    @pytest.mark.asyncio
    async def test_exchange_health_alert(self):
        """Unhealthy exchange health output -> high alert."""
        upstream = {
            "exchange_health": _make_upstream(
                "exchange_health",
                {
                    "exchange_status": "DOWN",
                    "is_healthy": False,
                    "latency_ms": 5000,
                    "degraded_services": ["order_book"],
                },
                confidence=0.90,
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        exchange_alerts = [
            a for a in result.output["alerts"]
            if a["source_skill"] == "exchange_health"
        ]
        assert len(exchange_alerts) >= 1
        assert exchange_alerts[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_alerts_sorted_by_severity(self):
        """Alerts should be sorted by severity: critical -> high -> medium -> low -> info."""
        upstream = {
            "skill_a": _make_upstream(
                "skill_a", {}, status=SkillStatus.ERROR,
                confidence=None, message="error",
            ),
            "skill_b": _make_upstream(
                "skill_b", {"data": 1}, confidence=0.25,
            ),
            "skill_c": _make_upstream(
                "skill_c", {"data": 2}, confidence=0.80,
                requires_human_review=True,
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        alert_severities = [
            severity_order.get(a["severity"], 5)
            for a in result.output["alerts"]
        ]
        assert alert_severities == sorted(alert_severities)

    @pytest.mark.asyncio
    async def test_alert_deduplication(self):
        """Duplicate alerts should be deduplicated."""
        upstream = {
            "skill_a": _make_upstream(
                "skill_a", {}, status=SkillStatus.FAILURE,
                confidence=None, message="data missing",
            ),
        }
        ctx = _make_context(upstream_results=upstream)

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        # Check that no two alerts share (severity, source_skill, message).
        seen = set()
        for alert in result.output["alerts"]:
            key = (alert["severity"], alert["source_skill"], alert["message"])
            assert key not in seen, f"Duplicate alert found: {key}"
            seen.add(key)

    @pytest.mark.asyncio
    async def test_no_upstream_results_no_alerts(self):
        """No upstream results at all -> zero alerts."""
        ctx = _make_context(upstream_results={})

        skill = AlertGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["alert_count"] == 0
        assert result.output["alerts"] == []

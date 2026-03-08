"""
Unit tests for the 7 failure-analysis agent skills.

Each skill receives a SkillContext and returns a SkillResult.
Tests cover SUCCESS, FAILURE, and SKIPPED outcomes.
"""

import pytest
from decimal import Decimal

from app.agents.types import (
    AgentType,
    SkillContext,
    SkillResult,
    SkillStatus,
)
from app.agents.analysis_agent.skills.incident_detection import (
    IncidentDetectionSkill,
)
from app.agents.analysis_agent.skills.timeline_reconstruction import (
    TimelineReconstructionSkill,
)
from app.agents.analysis_agent.skills.root_cause_classification import (
    RootCauseClassificationSkill,
)
from app.agents.analysis_agent.skills.counterfactual_analysis import (
    CounterfactualAnalysisSkill,
)
from app.agents.analysis_agent.skills.recommendation_generation import (
    RecommendationGenerationSkill,
)
from app.agents.analysis_agent.skills.lesson_extraction import (
    LessonExtractionSkill,
)
from app.agents.analysis_agent.skills.report_writing import (
    ReportWritingSkill,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_ORDER_HISTORY = [
    {
        "order_id": "ord-001",
        "status": "FILLED",
        "side": "BUY",
        "symbol": "BTCUSDT",
        "quantity": "0.5",
        "timestamp": "2025-01-10T10:00:00Z",
        "order_type": "LIMIT",
        "filled_price": "50000",
        "expected_price": "50000",
        "realized_pnl": "200",
        "entry_value": "25000",
    },
    {
        "order_id": "ord-002",
        "status": "REJECTED",
        "side": "BUY",
        "symbol": "ETHUSDT",
        "quantity": "10",
        "timestamp": "2025-01-10T10:05:00Z",
        "reason": "risk limit exceeded",
        "order_type": "MARKET",
    },
    {
        "order_id": "ord-003",
        "status": "FAILED",
        "side": "SELL",
        "symbol": "SOLUSDT",
        "quantity": "100",
        "timestamp": "2025-01-10T10:10:00Z",
        "reason": "exchange error: timeout",
        "error_code": "E_TIMEOUT",
        "order_type": "MARKET",
    },
    {
        "order_id": "ord-004",
        "status": "FILLED",
        "side": "SELL",
        "symbol": "BTCUSDT",
        "quantity": "1.0",
        "timestamp": "2025-01-10T10:15:00Z",
        "order_type": "MARKET",
        "filled_price": "48500",
        "expected_price": "50000",
        "realized_pnl": "-1500",
        "entry_value": "50000",
    },
]


def _make_analysis_context(
    *,
    order_history: list | None = None,
    upstream_results: dict[str, SkillResult] | None = None,
) -> SkillContext:
    """Build a SkillContext with sensible defaults for analysis-agent tests."""
    return SkillContext(
        agent_type=AgentType.FAILURE_ANALYSIS,
        symbol="BTCUSDT",
        order_history=order_history if order_history is not None else list(_SAMPLE_ORDER_HISTORY),
        upstream_results=upstream_results or {},
    )


def _make_upstream(
    skill_id: str,
    output: dict,
    *,
    status: SkillStatus = SkillStatus.SUCCESS,
    confidence: float | None = 0.85,
    message: str = "",
) -> SkillResult:
    """Shorthand for building an upstream SkillResult."""
    return SkillResult(
        skill_id=skill_id,
        status=status,
        output=output,
        message=message,
        confidence=confidence,
    )


async def _run_incident_detection(
    order_history: list | None = None,
) -> SkillResult:
    """Run IncidentDetectionSkill and return its result."""
    skill = IncidentDetectionSkill()
    ctx = _make_analysis_context(order_history=order_history)
    return await skill.execute(ctx)


async def _build_upstream_chain_through(
    target: str,
    order_history: list | None = None,
) -> dict[str, SkillResult]:
    """
    Run the analysis pipeline up to (but not including) *target* and return
    the accumulated upstream_results dict.

    Supported targets: timeline_reconstruction, root_cause_classification,
    counterfactual_analysis, recommendation_generation, lesson_extraction,
    report_writing.
    """
    oh = order_history if order_history is not None else list(_SAMPLE_ORDER_HISTORY)
    upstream: dict[str, SkillResult] = {}

    # incident_detection
    inc_skill = IncidentDetectionSkill()
    inc_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    inc_result = await inc_skill.execute(inc_ctx)
    upstream["incident_detection"] = inc_result
    if target == "timeline_reconstruction":
        return upstream

    # timeline_reconstruction
    tl_skill = TimelineReconstructionSkill()
    tl_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    tl_result = await tl_skill.execute(tl_ctx)
    upstream["timeline_reconstruction"] = tl_result
    if target == "root_cause_classification":
        return upstream

    # root_cause_classification
    rc_skill = RootCauseClassificationSkill()
    rc_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    rc_result = await rc_skill.execute(rc_ctx)
    upstream["root_cause_classification"] = rc_result
    if target == "counterfactual_analysis":
        return upstream

    # counterfactual_analysis
    cf_skill = CounterfactualAnalysisSkill()
    cf_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    cf_result = await cf_skill.execute(cf_ctx)
    upstream["counterfactual_analysis"] = cf_result
    if target == "recommendation_generation":
        return upstream

    # recommendation_generation
    rg_skill = RecommendationGenerationSkill()
    rg_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    rg_result = await rg_skill.execute(rg_ctx)
    upstream["recommendation_generation"] = rg_result
    if target == "lesson_extraction":
        return upstream

    # lesson_extraction
    le_skill = LessonExtractionSkill()
    le_ctx = _make_analysis_context(order_history=oh, upstream_results=upstream)
    le_result = await le_skill.execute(le_ctx)
    upstream["lesson_extraction"] = le_result
    if target == "report_writing":
        return upstream

    return upstream


# ===========================================================================
# IncidentDetectionSkill
# ===========================================================================


class TestIncidentDetectionSkill:
    """Tests for the incident detection skill."""

    @pytest.mark.asyncio
    async def test_no_incidents_for_clean_history(self):
        """All orders FILLED with no issues -> zero incidents, SUCCESS."""
        clean_orders = [
            {
                "order_id": "clean-1",
                "status": "FILLED",
                "side": "BUY",
                "symbol": "BTCUSDT",
                "quantity": "0.1",
                "timestamp": "2025-01-10T10:00:00Z",
                "realized_pnl": "50",
                "entry_value": "5000",
                "expected_price": "50000",
                "filled_price": "50000",
            }
        ]
        result = await _run_incident_detection(order_history=clean_orders)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["total_count"] == 0
        assert result.output["incidents"] == []

    @pytest.mark.asyncio
    async def test_rejected_order_detected(self):
        """A REJECTED order should produce a 'rejected_order' incident."""
        orders = [
            {
                "order_id": "rej-1",
                "status": "REJECTED",
                "reason": "insufficient balance",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["total_count"] >= 1
        types = [i["type"] for i in result.output["incidents"]]
        assert "rejected_order" in types

    @pytest.mark.asyncio
    async def test_failed_order_detected(self):
        """A FAILED order should produce a 'failed_order' incident."""
        orders = [
            {
                "order_id": "fail-1",
                "status": "FAILED",
                "reason": "connection lost",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "failed_order" in types

    @pytest.mark.asyncio
    async def test_exchange_rejection_via_error_code(self):
        """An order with error_code should produce 'exchange_rejection' incident."""
        orders = [
            {
                "order_id": "exch-1",
                "status": "REJECTED",
                "reason": "rate limit",
                "error_code": "E_RATE_LIMIT",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "exchange_rejection" in types

    @pytest.mark.asyncio
    async def test_large_loss_detected(self):
        """A loss > 2 % should produce a 'large_loss' incident."""
        orders = [
            {
                "order_id": "loss-1",
                "status": "FILLED",
                "realized_pnl": "-600",
                "entry_value": "10000",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "large_loss" in types

    @pytest.mark.asyncio
    async def test_large_loss_not_triggered_below_threshold(self):
        """A loss <= 2 % should NOT produce a 'large_loss' incident."""
        orders = [
            {
                "order_id": "small-loss-1",
                "status": "FILLED",
                "realized_pnl": "-100",
                "entry_value": "10000",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "large_loss" not in types

    @pytest.mark.asyncio
    async def test_slippage_breach_detected(self):
        """Slippage > 0.5 % should produce 'slippage_breach' incident."""
        orders = [
            {
                "order_id": "slip-1",
                "status": "FILLED",
                "expected_price": "50000",
                "filled_price": "50300",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "slippage_breach" in types

    @pytest.mark.asyncio
    async def test_slippage_not_triggered_below_threshold(self):
        """Slippage <= 0.5 % should NOT produce 'slippage_breach' incident."""
        orders = [
            {
                "order_id": "ok-slip-1",
                "status": "FILLED",
                "expected_price": "50000",
                "filled_price": "50100",
                "timestamp": "2025-01-10T10:00:00Z",
            }
        ]
        result = await _run_incident_detection(order_history=orders)

        assert result.status == SkillStatus.SUCCESS
        types = [i["type"] for i in result.output["incidents"]]
        assert "slippage_breach" not in types

    @pytest.mark.asyncio
    async def test_empty_order_history_skips(self):
        """Empty order_history -> SKIPPED."""
        result = await _run_incident_detection(order_history=[])

        assert result.status == SkillStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_mixed_history_detects_multiple_incidents(self):
        """The sample history should produce multiple incidents."""
        result = await _run_incident_detection()

        assert result.status == SkillStatus.SUCCESS
        assert result.output["total_count"] >= 3  # rejected + failed + exchange + slippage
        # Incidents should be sorted by priority descending.
        scores = [i["priority_score"] for i in result.output["incidents"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_skill_metadata(self):
        """Verify skill metadata properties."""
        skill = IncidentDetectionSkill()
        assert skill.skill_id == "incident_detection"
        assert "order_history" in skill.required_inputs
        assert skill.prerequisites == []


# ===========================================================================
# TimelineReconstructionSkill
# ===========================================================================


class TestTimelineReconstructionSkill:
    """Tests for the timeline reconstruction skill."""

    @pytest.mark.asyncio
    async def test_basic_timeline_no_incidents(self):
        """Clean orders -> timeline with order events only."""
        clean_orders = [
            {
                "order_id": "t-1",
                "status": "FILLED",
                "side": "BUY",
                "symbol": "BTCUSDT",
                "quantity": "1",
                "timestamp": "2025-01-10T10:00:00Z",
            },
            {
                "order_id": "t-2",
                "status": "FILLED",
                "side": "SELL",
                "symbol": "BTCUSDT",
                "quantity": "1",
                "timestamp": "2025-01-10T11:00:00Z",
            },
        ]
        # Build upstream with no incidents.
        inc_result = _make_upstream(
            "incident_detection",
            {"incidents": [], "total_count": 0},
        )
        ctx = _make_analysis_context(
            order_history=clean_orders,
            upstream_results={"incident_detection": inc_result},
        )

        skill = TimelineReconstructionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["event_count"] == 2
        assert len(result.output["timeline"]) == 2
        assert result.output["duration_span"] != ""

    @pytest.mark.asyncio
    async def test_timeline_with_incidents(self):
        """Orders + upstream incidents -> merged timeline with incident events."""
        upstream = await _build_upstream_chain_through("timeline_reconstruction")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = TimelineReconstructionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        # Should have both order events and incident events.
        event_types = [e["event_type"] for e in result.output["timeline"]]
        order_events = [et for et in event_types if et.startswith("order_")]
        incident_events = [et for et in event_types if et.startswith("incident_")]
        assert len(order_events) >= 1
        assert len(incident_events) >= 1
        # Timeline should be chronologically sorted.
        timestamps = [e["timestamp"] for e in result.output["timeline"]]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_empty_order_history_skips(self):
        """Empty order_history -> SKIPPED."""
        inc_result = _make_upstream(
            "incident_detection",
            {"incidents": [], "total_count": 0},
        )
        ctx = _make_analysis_context(
            order_history=[],
            upstream_results={"incident_detection": inc_result},
        )

        skill = TimelineReconstructionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_incident_order_ids_cross_referenced(self):
        """Order details should have is_incident=True for incident orders."""
        upstream = await _build_upstream_chain_through("timeline_reconstruction")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = TimelineReconstructionSkill()
        result = await skill.execute(ctx)

        # Find order events that are incidents.
        incident_flags = [
            e["details"].get("is_incident", False)
            for e in result.output["timeline"]
            if e["event_type"].startswith("order_")
        ]
        assert any(incident_flags), "Expected at least one order flagged as incident"

    @pytest.mark.asyncio
    async def test_skill_metadata(self):
        """Verify skill metadata properties."""
        skill = TimelineReconstructionSkill()
        assert skill.skill_id == "timeline_reconstruction"
        assert "incident_detection" in skill.prerequisites


# ===========================================================================
# RootCauseClassificationSkill
# ===========================================================================


class TestRootCauseClassificationSkill:
    """Tests for the root cause classification skill."""

    @pytest.mark.asyncio
    async def test_exchange_error_classified(self):
        """exchange_rejection incident -> classified as 'exchange'."""
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "exchange_rejection",
                        "order_id": "exch-1",
                        "reason": "Exchange error: E_TIMEOUT",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.7,
                    }
                ],
                "total_count": 1,
            },
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        categories = [rc["category"] for rc in result.output["root_causes"]]
        assert "exchange" in categories

    @pytest.mark.asyncio
    async def test_slippage_classified_as_execution(self):
        """slippage_breach incident -> classified as 'execution'."""
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "slippage_breach",
                        "order_id": "slip-1",
                        "reason": "Slippage of 1.20%",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.5,
                    }
                ],
                "total_count": 1,
            },
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        categories = [rc["category"] for rc in result.output["root_causes"]]
        assert "execution" in categories

    @pytest.mark.asyncio
    async def test_risk_rejection_classified_as_risk_control(self):
        """Rejected order with risk-related reason -> 'risk_control'."""
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "rejected_order",
                        "order_id": "risk-1",
                        "reason": "risk limit exceeded",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.4,
                    }
                ],
                "total_count": 1,
            },
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        categories = [rc["category"] for rc in result.output["root_causes"]]
        assert "risk_control" in categories

    @pytest.mark.asyncio
    async def test_unknown_fallback(self):
        """Incident with no matching rule/keyword -> 'unknown'."""
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "failed_order",
                        "order_id": "unk-1",
                        "reason": "something completely unexpected happened",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.6,
                    }
                ],
                "total_count": 1,
            },
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        categories = [rc["category"] for rc in result.output["root_causes"]]
        assert "unknown" in categories

    @pytest.mark.asyncio
    async def test_no_incident_data_skips(self):
        """Missing incident_detection upstream -> SKIPPED."""
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={"timeline_reconstruction": tl_result}
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_empty_incidents_returns_empty_root_causes(self):
        """Incident detection ran but found no incidents -> empty root_causes."""
        inc_result = _make_upstream(
            "incident_detection",
            {"incidents": [], "total_count": 0},
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["root_causes"] == []

    @pytest.mark.asyncio
    async def test_root_causes_sorted_by_confidence(self):
        """Root causes should be sorted by confidence descending."""
        upstream = await _build_upstream_chain_through("root_cause_classification")
        # Re-run classification to inspect ordering.
        skill = RootCauseClassificationSkill()
        ctx = _make_analysis_context(upstream_results=upstream)
        result = await skill.execute(ctx)

        if result.output["root_causes"]:
            confidences = [rc["confidence"] for rc in result.output["root_causes"]]
            assert confidences == sorted(confidences, reverse=True)

    @pytest.mark.asyncio
    async def test_large_loss_with_keyword_match(self):
        """Large loss with a keyword in reason -> matched category."""
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "large_loss",
                        "order_id": "ll-1",
                        "reason": "Loss of -5.00% due to volatility spike",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.9,
                    }
                ],
                "total_count": 1,
            },
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
            }
        )

        skill = RootCauseClassificationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        categories = [rc["category"] for rc in result.output["root_causes"]]
        assert "market" in categories


# ===========================================================================
# CounterfactualAnalysisSkill
# ===========================================================================


class TestCounterfactualAnalysisSkill:
    """Tests for the counterfactual analysis skill."""

    @pytest.mark.asyncio
    async def test_basic_scenarios_generated(self):
        """Incidents present -> 4 scenarios per incident."""
        upstream = await _build_upstream_chain_through("counterfactual_analysis")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = CounterfactualAnalysisSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        scenarios = result.output["scenarios"]
        assert len(scenarios) >= 4  # At least 4 for one incident
        scenario_names = {s["name"] for s in scenarios}
        assert "half_size" in scenario_names
        assert "delayed_entry_1min" in scenario_names
        assert "limit_instead_of_market" in scenario_names
        assert "skip_trade" in scenario_names

    @pytest.mark.asyncio
    async def test_no_incidents_produces_empty_scenarios(self):
        """No incidents -> empty scenarios list, SUCCESS."""
        inc_result = _make_upstream(
            "incident_detection",
            {"incidents": [], "total_count": 0},
        )
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "root_cause_classification": rc_result,
            }
        )

        skill = CounterfactualAnalysisSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["scenarios"] == []

    @pytest.mark.asyncio
    async def test_no_incident_data_skips(self):
        """Missing incident_detection upstream -> SKIPPED."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": []},
        )
        ctx = _make_analysis_context(
            upstream_results={"root_cause_classification": rc_result}
        )

        skill = CounterfactualAnalysisSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_scenarios_contain_required_keys(self):
        """Every scenario should have name, estimated_outcome, likely_improvement."""
        upstream = await _build_upstream_chain_through("counterfactual_analysis")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = CounterfactualAnalysisSkill()
        result = await skill.execute(ctx)

        for sc in result.output["scenarios"]:
            assert "name" in sc
            assert "estimated_outcome" in sc
            assert "likely_improvement" in sc
            assert "order_id" in sc

    @pytest.mark.asyncio
    async def test_half_size_with_pnl_data(self):
        """Half-size scenario with PnL data should compute estimated PnL."""
        orders = [
            {
                "order_id": "pnl-1",
                "status": "FILLED",
                "side": "SELL",
                "symbol": "BTCUSDT",
                "quantity": "1",
                "timestamp": "2025-01-10T10:00:00Z",
                "order_type": "MARKET",
                "realized_pnl": "-1000",
                "entry_value": "20000",
                "expected_price": "50000",
                "filled_price": "50500",
            },
        ]
        inc_result = _make_upstream(
            "incident_detection",
            {
                "incidents": [
                    {
                        "type": "large_loss",
                        "order_id": "pnl-1",
                        "reason": "Loss of -5.00%",
                        "timestamp": "2025-01-10T10:00:00Z",
                        "priority_score": 0.9,
                    }
                ],
                "total_count": 1,
            },
        )
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": [{"category": "market", "confidence": 0.6, "evidence": "test"}]},
        )
        ctx = _make_analysis_context(
            order_history=orders,
            upstream_results={
                "incident_detection": inc_result,
                "root_cause_classification": rc_result,
            },
        )

        skill = CounterfactualAnalysisSkill()
        result = await skill.execute(ctx)

        half_size = [s for s in result.output["scenarios"] if s["name"] == "half_size"]
        assert len(half_size) == 1
        assert half_size[0]["likely_improvement"] == "high"


# ===========================================================================
# RecommendationGenerationSkill
# ===========================================================================


class TestRecommendationGenerationSkill:
    """Tests for the recommendation generation skill."""

    @pytest.mark.asyncio
    async def test_recommendations_generated_from_root_causes(self):
        """Root causes present -> recommendations generated."""
        upstream = await _build_upstream_chain_through("recommendation_generation")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = RecommendationGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert len(result.output["recommendations"]) >= 1
        for rec in result.output["recommendations"]:
            assert "type" in rec
            assert "description" in rec
            assert "priority" in rec

    @pytest.mark.asyncio
    async def test_no_root_causes_returns_empty(self):
        """No root causes -> empty recommendations."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": []},
        )
        cf_result = _make_upstream(
            "counterfactual_analysis",
            {"scenarios": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "counterfactual_analysis": cf_result,
            }
        )

        skill = RecommendationGenerationSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["recommendations"] == []

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Two root causes of same type -> deduplicated to one recommendation per type."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {
                "root_causes": [
                    {"category": "exchange", "confidence": 0.95, "evidence": "error 1"},
                    {"category": "exchange", "confidence": 0.80, "evidence": "error 2"},
                ]
            },
        )
        cf_result = _make_upstream(
            "counterfactual_analysis",
            {"scenarios": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "counterfactual_analysis": cf_result,
            }
        )

        skill = RecommendationGenerationSkill()
        result = await skill.execute(ctx)

        rec_types = [r["type"] for r in result.output["recommendations"]]
        # Should be deduplicated -- no duplicate types.
        assert len(rec_types) == len(set(rec_types))

    @pytest.mark.asyncio
    async def test_requires_human_review_flag(self):
        """Skill metadata should indicate human review is required."""
        skill = RecommendationGenerationSkill()
        assert skill.requires_human_review is True

    @pytest.mark.asyncio
    async def test_counterfactual_enrichment(self):
        """Recommendations enriched with counterfactual support when available."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {
                "root_causes": [
                    {"category": "sizing", "confidence": 0.85, "evidence": "large loss"},
                ]
            },
        )
        cf_result = _make_upstream(
            "counterfactual_analysis",
            {
                "scenarios": [
                    {
                        "order_id": "cf-1",
                        "name": "half_size",
                        "estimated_outcome": "loss halved",
                        "likely_improvement": "high",
                    },
                    {
                        "order_id": "cf-1",
                        "name": "skip_trade",
                        "estimated_outcome": "loss avoided",
                        "likely_improvement": "high",
                    },
                ]
            },
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "counterfactual_analysis": cf_result,
            }
        )

        skill = RecommendationGenerationSkill()
        result = await skill.execute(ctx)

        sizing_recs = [
            r for r in result.output["recommendations"]
            if r["type"] == "sizing_change"
        ]
        assert len(sizing_recs) == 1
        assert "counterfactual_support" in sizing_recs[0]


# ===========================================================================
# LessonExtractionSkill
# ===========================================================================


class TestLessonExtractionSkill:
    """Tests for the lesson extraction skill."""

    @pytest.mark.asyncio
    async def test_lessons_extracted(self):
        """Root causes present -> lessons extracted with title and category."""
        upstream = await _build_upstream_chain_through("lesson_extraction")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = LessonExtractionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert len(result.output["lessons"]) >= 1
        for lesson in result.output["lessons"]:
            assert "title" in lesson
            assert "category" in lesson
            assert "description" in lesson

    @pytest.mark.asyncio
    async def test_no_root_causes_returns_empty(self):
        """No root causes -> empty lessons."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": []},
        )
        rec_result = _make_upstream(
            "recommendation_generation",
            {"recommendations": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "recommendation_generation": rec_result,
            }
        )

        skill = LessonExtractionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["lessons"] == []

    @pytest.mark.asyncio
    async def test_lessons_have_specific_evidence(self):
        """Lessons enriched with evidence from root causes."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {
                "root_causes": [
                    {
                        "category": "exchange",
                        "confidence": 0.95,
                        "evidence": "Exchange rejection detected: E_TIMEOUT",
                    }
                ]
            },
        )
        rec_result = _make_upstream(
            "recommendation_generation",
            {
                "recommendations": [
                    {
                        "type": "monitoring_change",
                        "description": "Add exchange monitoring",
                        "priority": "high",
                    }
                ]
            },
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "recommendation_generation": rec_result,
            }
        )

        skill = LessonExtractionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        lesson = result.output["lessons"][0]
        assert "specific_evidence" in lesson
        assert "E_TIMEOUT" in lesson["specific_evidence"]

    @pytest.mark.asyncio
    async def test_linked_recommendations(self):
        """Lessons enriched with linked recommendation from upstream."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {
                "root_causes": [
                    {
                        "category": "execution",
                        "confidence": 0.85,
                        "evidence": "Slippage breach",
                    }
                ]
            },
        )
        rec_result = _make_upstream(
            "recommendation_generation",
            {
                "recommendations": [
                    {
                        "type": "execution_change",
                        "description": "Switch to limit orders",
                        "priority": "medium",
                    }
                ]
            },
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "recommendation_generation": rec_result,
            }
        )

        skill = LessonExtractionSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        lesson = result.output["lessons"][0]
        assert "linked_recommendation" in lesson

    @pytest.mark.asyncio
    async def test_deduplication_by_category(self):
        """Multiple root causes with same category -> single lesson."""
        rc_result = _make_upstream(
            "root_cause_classification",
            {
                "root_causes": [
                    {"category": "exchange", "confidence": 0.95, "evidence": "error 1"},
                    {"category": "exchange", "confidence": 0.80, "evidence": "error 2"},
                ]
            },
        )
        rec_result = _make_upstream(
            "recommendation_generation",
            {"recommendations": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "root_cause_classification": rc_result,
                "recommendation_generation": rec_result,
            }
        )

        skill = LessonExtractionSkill()
        result = await skill.execute(ctx)

        categories = [l["category"] for l in result.output["lessons"]]
        # Only one lesson for the 'exchange' category (mapped to 'infrastructure').
        assert len(categories) == len(set(categories))


# ===========================================================================
# ReportWritingSkill
# ===========================================================================


class TestReportWritingSkill:
    """Tests for the report writing skill."""

    @pytest.mark.asyncio
    async def test_report_generated_with_all_sections(self):
        """Full upstream chain -> report with all expected keys."""
        upstream = await _build_upstream_chain_through("report_writing")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = ReportWritingSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        output = result.output
        assert "summary" in output
        assert "root_causes" in output
        assert "recommendations" in output
        assert "lessons" in output
        assert "preventable" in output
        assert "human_review_needed" in output
        assert output["human_review_needed"] is True

    @pytest.mark.asyncio
    async def test_preventability_true_for_non_market_cause(self):
        """Non-market root causes -> preventable = True."""
        upstream = await _build_upstream_chain_through("report_writing")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = ReportWritingSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        # The sample data includes exchange and risk_control causes -> preventable.
        assert result.output["preventable"] is True

    @pytest.mark.asyncio
    async def test_preventability_false_for_market_only(self):
        """Only market root cause and no high-improvement scenarios -> preventable = False."""
        inc_result = _make_upstream(
            "incident_detection",
            {"incidents": [{"type": "large_loss", "order_id": "m-1"}], "total_count": 1},
        )
        tl_result = _make_upstream(
            "timeline_reconstruction",
            {"timeline": [], "event_count": 0, "duration_span": ""},
        )
        rc_result = _make_upstream(
            "root_cause_classification",
            {"root_causes": [{"category": "market", "confidence": 0.60, "evidence": "test"}]},
        )
        cf_result = _make_upstream(
            "counterfactual_analysis",
            {"scenarios": [{"name": "half_size", "likely_improvement": "low"}]},
        )
        rec_result = _make_upstream(
            "recommendation_generation",
            {"recommendations": []},
        )
        le_result = _make_upstream(
            "lesson_extraction",
            {"lessons": []},
        )
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
                "root_cause_classification": rc_result,
                "counterfactual_analysis": cf_result,
                "recommendation_generation": rec_result,
                "lesson_extraction": le_result,
            }
        )

        skill = ReportWritingSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["preventable"] is False

    @pytest.mark.asyncio
    async def test_summary_contains_incident_count(self):
        """Summary text should mention the incident count."""
        upstream = await _build_upstream_chain_through("report_writing")
        ctx = _make_analysis_context(upstream_results=upstream)

        skill = ReportWritingSkill()
        result = await skill.execute(ctx)

        assert "incident" in result.output["summary"].lower()

    @pytest.mark.asyncio
    async def test_report_with_no_upstream_data(self):
        """All upstream results empty -> report still produced (empty sections)."""
        inc_result = _make_upstream("incident_detection", {})
        tl_result = _make_upstream("timeline_reconstruction", {})
        rc_result = _make_upstream("root_cause_classification", {})
        cf_result = _make_upstream("counterfactual_analysis", {})
        rec_result = _make_upstream("recommendation_generation", {})
        le_result = _make_upstream("lesson_extraction", {})
        ctx = _make_analysis_context(
            upstream_results={
                "incident_detection": inc_result,
                "timeline_reconstruction": tl_result,
                "root_cause_classification": rc_result,
                "counterfactual_analysis": cf_result,
                "recommendation_generation": rec_result,
                "lesson_extraction": le_result,
            }
        )

        skill = ReportWritingSkill()
        result = await skill.execute(ctx)

        assert result.status == SkillStatus.SUCCESS
        assert result.output["preventable"] is False

    @pytest.mark.asyncio
    async def test_requires_human_review_flag(self):
        """Skill metadata should indicate human review is required."""
        skill = ReportWritingSkill()
        assert skill.requires_human_review is True

"""
Unit tests for all 9 trade decision agent skills.

Each test directly instantiates a skill and calls ``await skill.execute(ctx)``,
then asserts the result status, output keys, message, and confidence where
applicable.

Conventions:
  - pytest function style (no classes).
  - ``@pytest.mark.asyncio`` on every async test for explicitness.
  - ``_make_context(**overrides)`` helper to build a SkillContext with
    sensible defaults.
  - Per-skill upstream result helpers for prerequisite chaining.
"""

from __future__ import annotations

import pytest
from decimal import Decimal

from app.agents.types import (
    SkillContext,
    SkillResult,
    SkillStatus,
)
from app.agents.trade_agent.skills.budget_interpretation import BudgetInterpretationSkill
from app.agents.trade_agent.skills.market_context import MarketContextSkill
from app.agents.trade_agent.skills.opportunity_scoring import OpportunityScoringSkill
from app.agents.trade_agent.skills.position_sizing import PositionSizingSkill
from app.agents.trade_agent.skills.entry_planning import EntryPlanningSkill
from app.agents.trade_agent.skills.risk_precheck import RiskPrecheckSkill
from app.agents.trade_agent.skills.trade_decision import TradeDecisionSkill
from app.agents.trade_agent.skills.no_trade_justification import NoTradeJustificationSkill
from app.agents.trade_agent.skills.execution_review import ExecutionReviewSkill


# ---------------------------------------------------------------------------
# Context factory
# ---------------------------------------------------------------------------

def _make_context(**overrides) -> SkillContext:
    """Build a SkillContext with sensible defaults for testing."""
    defaults = dict(
        symbols=["BTCUSDT"],
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
            },
        },
        budget={
            "max_deployment_pct": "0.8",
            "per_symbol_max_pct": "0.2",
        },
        available_capital=Decimal("10000"),
        total_portfolio_value=Decimal("20000"),
        current_positions={},
        risk_state={},
        settings={
            "MAX_ORDER_NOTIONAL": "10000",
            "MAX_POSITION_NOTIONAL": "50000",
            "SYMBOL_WHITELIST": ["BTCUSDT", "ETHUSDT"],
        },
        trading_mode="PAPER",
        upstream_results={},
    )
    defaults.update(overrides)
    return SkillContext(**defaults)


# ---------------------------------------------------------------------------
# Upstream result helpers -- simulate prerequisite outputs for chaining
# ---------------------------------------------------------------------------

def _budget_result(
    available: str = "10000",
    deployable: str = "8000",
    per_symbol: str = "2000",
) -> SkillResult:
    """Simulate a successful BudgetInterpretationSkill result."""
    return SkillResult(
        skill_id="budget_interpretation",
        status=SkillStatus.SUCCESS,
        output={
            "available_capital": available,
            "deployable_capital": deployable,
            "per_symbol_limit": per_symbol,
            "reserved_capital": str(Decimal(available) - Decimal(deployable)),
            "max_deployment_pct": "0.8",
            "per_symbol_max_pct": "0.2",
        },
        message="Budget interpreted.",
    )


def _market_context_result(
    symbol: str = "BTCUSDT",
    spread_class: str = "tight",
    spread_pct: str = "0.00004",
    volume: str = "1000000",
    low_liquidity: bool = False,
    bid: str = "49999",
    ask: str = "50001",
    mid: str = "50000",
    last: str = "50000",
) -> SkillResult:
    """Simulate a successful MarketContextSkill result."""
    return SkillResult(
        skill_id="market_context",
        status=SkillStatus.SUCCESS,
        output={
            "symbol_contexts": [
                {
                    "symbol": symbol,
                    "last_price": last,
                    "bid_price": bid,
                    "ask_price": ask,
                    "mid_price": mid,
                    "spread_abs": str(Decimal(ask) - Decimal(bid)),
                    "spread_pct": spread_pct,
                    "spread_class": spread_class,
                    "volume_24h": volume,
                    "low_liquidity": low_liquidity,
                },
            ],
            "num_symbols": 1,
        },
        message="Market context computed.",
    )


def _opportunity_scoring_result(
    symbol: str = "BTCUSDT",
    score: float = 75.0,
    no_trade: bool = False,
) -> SkillResult:
    """Simulate a successful OpportunityScoringSkill result."""
    return SkillResult(
        skill_id="opportunity_scoring",
        status=SkillStatus.SUCCESS,
        output={
            "ranked_candidates": [
                {
                    "symbol": symbol,
                    "score": score,
                    "spread_score": 100.0,
                    "volume_score": 85.0,
                    "momentum_score": 50.0,
                    "low_liquidity": False,
                },
            ],
            "no_trade": no_trade,
            "best_score": score,
            "threshold": 30,
        },
        message="Scored.",
    )


def _position_sizing_result(
    symbol: str = "BTCUSDT",
    quantity: str = "0.01000000",
    notional: str = "500.00000000",
    no_alloc: bool = False,
) -> SkillResult:
    """Simulate a successful PositionSizingSkill result."""
    allocations = {}
    if not no_alloc:
        allocations = {
            symbol: {
                "quantity": quantity,
                "notional": notional,
                "pct_of_budget": "6.25",
            },
        }
    return SkillResult(
        skill_id="position_sizing",
        status=SkillStatus.SUCCESS,
        output={
            "allocations": allocations,
            "sizing_method": "equal_risk" if not no_alloc else "none",
            "residual_cash": "7500",
        },
        message="Sized.",
    )


def _entry_planning_result(
    symbol: str = "BTCUSDT",
    order_type: str = "MARKET",
    quantity: str = "0.01000000",
    price: str | None = None,
) -> SkillResult:
    """Simulate a successful EntryPlanningSkill result."""
    plan = {
        "symbol": symbol,
        "side": "BUY",
        "order_type": order_type,
        "price": price,
        "quantity": quantity,
        "rationale": "test",
    }
    return SkillResult(
        skill_id="entry_planning",
        status=SkillStatus.SUCCESS,
        output={
            "order_plans": [plan],
            "num_orders": 1,
        },
        message="Planned.",
    )


def _risk_precheck_result(
    allowed: bool = True,
    symbol: str = "BTCUSDT",
    quantity: str = "0.01000000",
) -> SkillResult:
    """Simulate a successful (or failed) RiskPrecheckSkill result."""
    if allowed:
        checked_order = {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "price": None,
            "quantity": quantity,
            "rationale": "test",
            "allowed": True,
            "violations": [],
            "estimated_notional": "500",
        }
        return SkillResult(
            skill_id="risk_precheck",
            status=SkillStatus.SUCCESS,
            output={
                "checked_orders": [checked_order],
                "triggered_rules": [],
                "allowed_count": 1,
                "denied_count": 0,
            },
            message="All pass.",
        )
    else:
        checked_order = {
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "price": None,
            "quantity": quantity,
            "rationale": "test",
            "allowed": False,
            "violations": ["kill_switch_active"],
            "estimated_notional": "500",
        }
        return SkillResult(
            skill_id="risk_precheck",
            status=SkillStatus.FAILURE,
            message="All orders denied.",
            details={
                "checked_orders": [checked_order],
                "triggered_rules": [
                    {"symbol": symbol, "violations": ["kill_switch_active"]},
                ],
            },
        )


def _trade_decision_result(
    decision: str = "TRADE",
    symbol: str = "BTCUSDT",
) -> SkillResult:
    """Simulate a successful TradeDecisionSkill result."""
    if decision == "TRADE":
        return SkillResult(
            skill_id="trade_decision",
            status=SkillStatus.SUCCESS,
            output={
                "decision": "TRADE",
                "selected_orders": [
                    {
                        "symbol": symbol,
                        "side": "BUY",
                        "order_type": "MARKET",
                        "price": None,
                        "quantity": "0.01000000",
                        "allowed": True,
                        "violations": [],
                        "estimated_notional": "500",
                    },
                ],
                "confidence": 0.75,
                "reasoning_summary": "1 order(s) selected. Best opportunity score: 75.0.",
            },
            message="TRADE decision.",
        )
    else:
        return SkillResult(
            skill_id="trade_decision",
            status=SkillStatus.SUCCESS,
            output={
                "decision": "NO_TRADE",
                "selected_orders": [],
                "confidence": 1.0,
                "reasoning_summary": "Risk precheck denied all planned orders.",
            },
            message="NO_TRADE.",
        )


# ===========================================================================
# 1. BudgetInterpretationSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_budget_interpretation_valid_budget():
    """Default budget should produce correct deployable capital and per-symbol limit."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context()
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.skill_id == "budget_interpretation"
    output = result.output
    assert output["deployable_capital"] == "8000.0"
    assert output["per_symbol_limit"] == "2000.0"
    assert output["reserved_capital"] == "2000.0"
    assert output["max_deployment_pct"] == "0.8"
    assert output["per_symbol_max_pct"] == "0.2"


@pytest.mark.asyncio
async def test_budget_interpretation_custom_percentages():
    """Custom pct values should be honoured."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context(
        budget={"max_deployment_pct": "0.5", "per_symbol_max_pct": "0.1"},
        available_capital=Decimal("20000"),
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["deployable_capital"] == "10000.0"
    assert result.output["per_symbol_limit"] == "2000.0"


@pytest.mark.asyncio
async def test_budget_interpretation_clamps_above_one():
    """Percentages above 1 should be clamped to 1."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context(
        budget={"max_deployment_pct": "1.5", "per_symbol_max_pct": "2.0"},
        available_capital=Decimal("10000"),
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["max_deployment_pct"] == "1"
    assert result.output["per_symbol_max_pct"] == "1"
    assert result.output["deployable_capital"] == "10000"


@pytest.mark.asyncio
async def test_budget_interpretation_clamps_below_zero():
    """Negative percentages should be clamped to 0."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context(
        budget={"max_deployment_pct": "-0.5", "per_symbol_max_pct": "-1"},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["max_deployment_pct"] == "0"
    assert result.output["per_symbol_max_pct"] == "0"
    assert result.output["deployable_capital"] == "0"
    assert result.output["per_symbol_limit"] == "0"


def test_budget_interpretation_can_run_missing_budget():
    """can_run should fail when budget is empty."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context(budget={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "budget" in reason.lower()


def test_budget_interpretation_can_run_happy():
    """can_run should succeed with valid context."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context()
    ok, reason = skill.can_run(ctx)
    assert ok
    assert reason == ""


# ===========================================================================
# 2. MarketContextSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_market_context_tight_spread():
    """Bid/ask within 0.1% of mid should classify as tight."""
    skill = MarketContextSkill()
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
            },
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    sc = result.output["symbol_contexts"][0]
    assert sc["spread_class"] == "tight"
    assert sc["low_liquidity"] is False


@pytest.mark.asyncio
async def test_market_context_moderate_spread():
    """Spread between 0.1% and 0.5% should classify as moderate."""
    skill = MarketContextSkill()
    # spread = (50100 - 49900) / 50000 = 200/50000 = 0.004 = 0.4%
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49900",
                "ask_price": "50100",
                "volume_24h": "1000000",
            },
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    sc = result.output["symbol_contexts"][0]
    assert sc["spread_class"] == "moderate"


@pytest.mark.asyncio
async def test_market_context_wide_spread():
    """Spread >= 0.5% should classify as wide."""
    skill = MarketContextSkill()
    # spread = (50500 - 49500) / 50000 = 1000/50000 = 0.02 = 2%
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49500",
                "ask_price": "50500",
                "volume_24h": "1000000",
            },
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    sc = result.output["symbol_contexts"][0]
    assert sc["spread_class"] == "wide"


@pytest.mark.asyncio
async def test_market_context_low_liquidity():
    """Volume under 50000 should flag low_liquidity."""
    skill = MarketContextSkill()
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "10000",
            },
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    sc = result.output["symbol_contexts"][0]
    assert sc["low_liquidity"] is True


@pytest.mark.asyncio
async def test_market_context_missing_symbol_data():
    """Missing market data for a symbol should yield zeros / defaults."""
    skill = MarketContextSkill()
    ctx = _make_context(
        symbols=["BTCUSDT", "XYZUSDT"],
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
            },
            # XYZUSDT intentionally missing
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["num_symbols"] == 2
    xyz_ctx = [
        sc for sc in result.output["symbol_contexts"] if sc["symbol"] == "XYZUSDT"
    ][0]
    assert xyz_ctx["last_price"] == "0"
    assert xyz_ctx["low_liquidity"] is True


def test_market_context_can_run_missing_symbols():
    """can_run should fail when symbols list is empty."""
    skill = MarketContextSkill()
    ctx = _make_context(symbols=[])
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "symbols" in reason.lower()


@pytest.mark.asyncio
async def test_market_context_multiple_symbols():
    """Multiple symbols should all appear in output."""
    skill = MarketContextSkill()
    ctx = _make_context(
        symbols=["BTCUSDT", "ETHUSDT"],
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
            },
            "ETHUSDT": {
                "last_price": "3000",
                "bid_price": "2999",
                "ask_price": "3001",
                "volume_24h": "500000",
            },
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["num_symbols"] == 2
    syms = {sc["symbol"] for sc in result.output["symbol_contexts"]}
    assert syms == {"BTCUSDT", "ETHUSDT"}


# ===========================================================================
# 3. OpportunityScoringSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_opportunity_scoring_high_score():
    """Tight spread + high volume should yield a high score (above threshold)."""
    skill = OpportunityScoringSkill()
    ctx = _make_context(
        upstream_results={
            "market_context": _market_context_result(
                spread_class="tight",
                volume="1000000",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["no_trade"] is False
    assert result.output["best_score"] >= 30
    assert len(result.output["ranked_candidates"]) == 1
    assert result.output["ranked_candidates"][0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_opportunity_scoring_no_trade_low_score():
    """Wide spread + zero volume should yield a score below threshold."""
    skill = OpportunityScoringSkill()
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49500",
                "ask_price": "50500",
                "volume_24h": "0",
            },
        },
        upstream_results={
            "market_context": _market_context_result(
                spread_class="wide",
                volume="0",
                low_liquidity=True,
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["no_trade"] is True
    assert result.output["best_score"] < 30


@pytest.mark.asyncio
async def test_opportunity_scoring_ranking_order():
    """When multiple symbols, ranking should be descending by score."""
    skill = OpportunityScoringSkill()
    mc_result = SkillResult(
        skill_id="market_context",
        status=SkillStatus.SUCCESS,
        output={
            "symbol_contexts": [
                {
                    "symbol": "BTCUSDT",
                    "last_price": "50000",
                    "bid_price": "49999",
                    "ask_price": "50001",
                    "mid_price": "50000",
                    "spread_abs": "2",
                    "spread_pct": "0.00004",
                    "spread_class": "tight",
                    "volume_24h": "1000000",
                    "low_liquidity": False,
                },
                {
                    "symbol": "ETHUSDT",
                    "last_price": "3000",
                    "bid_price": "2950",
                    "ask_price": "3050",
                    "mid_price": "3000",
                    "spread_abs": "100",
                    "spread_pct": "0.0333",
                    "spread_class": "wide",
                    "volume_24h": "5000",
                    "low_liquidity": True,
                },
            ],
            "num_symbols": 2,
        },
        message="ok",
    )
    ctx = _make_context(
        symbols=["BTCUSDT", "ETHUSDT"],
        market_data={
            "BTCUSDT": {"last_price": "50000", "volume_24h": "1000000"},
            "ETHUSDT": {"last_price": "3000", "volume_24h": "5000"},
        },
        upstream_results={"market_context": mc_result},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    ranked = result.output["ranked_candidates"]
    assert len(ranked) == 2
    assert ranked[0]["score"] >= ranked[1]["score"]
    # BTC has tight spread and high volume -> should be ranked first.
    assert ranked[0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_opportunity_scoring_empty_symbol_contexts():
    """Empty symbol_contexts from market_context should produce FAILURE."""
    skill = OpportunityScoringSkill()
    mc_result = SkillResult(
        skill_id="market_context",
        status=SkillStatus.SUCCESS,
        output={"symbol_contexts": [], "num_symbols": 0},
        message="ok",
    )
    ctx = _make_context(
        upstream_results={"market_context": mc_result},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.FAILURE
    assert "no symbol" in result.message.lower()


@pytest.mark.asyncio
async def test_opportunity_scoring_with_momentum():
    """Positive momentum should boost score relative to neutral."""
    skill = OpportunityScoringSkill()
    ctx_no_momentum = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
            },
        },
        upstream_results={
            "market_context": _market_context_result(),
        },
    )
    ctx_high_momentum = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
                "momentum": 0.8,
            },
        },
        upstream_results={
            "market_context": _market_context_result(),
        },
    )
    result_neutral = await skill.execute(ctx_no_momentum)
    result_high = await skill.execute(ctx_high_momentum)

    neutral_score = result_neutral.output["best_score"]
    high_score = result_high.output["best_score"]
    assert high_score > neutral_score


# ===========================================================================
# 4. PositionSizingSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_position_sizing_basic_allocation():
    """Single tradeable candidate should receive an allocation."""
    skill = PositionSizingSkill()
    ctx = _make_context(
        upstream_results={
            "budget_interpretation": _budget_result(),
            "opportunity_scoring": _opportunity_scoring_result(score=75.0),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    allocs = result.output["allocations"]
    assert "BTCUSDT" in allocs
    assert Decimal(allocs["BTCUSDT"]["quantity"]) > 0
    assert Decimal(allocs["BTCUSDT"]["notional"]) > 0
    assert result.output["sizing_method"] == "equal_risk"


@pytest.mark.asyncio
async def test_position_sizing_no_trade_propagation():
    """When opportunity_scoring flags no_trade, allocations should be empty."""
    skill = PositionSizingSkill()
    ctx = _make_context(
        upstream_results={
            "budget_interpretation": _budget_result(),
            "opportunity_scoring": _opportunity_scoring_result(
                score=10.0, no_trade=True,
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["allocations"] == {}
    assert result.output["sizing_method"] == "none"


@pytest.mark.asyncio
async def test_position_sizing_volatility_aware():
    """When volatility data is present, sizing method should be volatility_aware."""
    skill = PositionSizingSkill()
    ctx = _make_context(
        market_data={
            "BTCUSDT": {
                "last_price": "50000",
                "bid_price": "49999",
                "ask_price": "50001",
                "volume_24h": "1000000",
                "volatility": "0.02",
            },
        },
        upstream_results={
            "budget_interpretation": _budget_result(),
            "opportunity_scoring": _opportunity_scoring_result(score=75.0),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["sizing_method"] == "volatility_aware"
    assert "BTCUSDT" in result.output["allocations"]


@pytest.mark.asyncio
async def test_position_sizing_caps_at_per_symbol_limit():
    """Allocation notional should not exceed per_symbol_limit."""
    skill = PositionSizingSkill()
    # Deployable = 80000 but per_symbol_limit = 2000.
    ctx = _make_context(
        available_capital=Decimal("100000"),
        upstream_results={
            "budget_interpretation": _budget_result(
                available="100000",
                deployable="80000",
                per_symbol="2000",
            ),
            "opportunity_scoring": _opportunity_scoring_result(score=90.0),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    allocs = result.output["allocations"]
    assert "BTCUSDT" in allocs
    actual_notional = Decimal(allocs["BTCUSDT"]["notional"])
    assert actual_notional <= Decimal("2000")


@pytest.mark.asyncio
async def test_position_sizing_empty_ranked():
    """Empty ranked candidates should produce no allocations."""
    skill = PositionSizingSkill()
    scoring_result = _opportunity_scoring_result(score=75.0)
    scoring_result.output["ranked_candidates"] = []
    ctx = _make_context(
        upstream_results={
            "budget_interpretation": _budget_result(),
            "opportunity_scoring": scoring_result,
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["allocations"] == {}


# ===========================================================================
# 5. EntryPlanningSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_entry_planning_market_order_tight_spread():
    """Tight spread (<0.1%) should produce a MARKET order."""
    skill = EntryPlanningSkill()
    ctx = _make_context(
        upstream_results={
            "position_sizing": _position_sizing_result(),
            "market_context": _market_context_result(
                spread_class="tight",
                spread_pct="0.00004",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    plans = result.output["order_plans"]
    assert len(plans) == 1
    assert plans[0]["order_type"] == "MARKET"
    assert plans[0]["price"] is None
    assert plans[0]["side"] == "BUY"


@pytest.mark.asyncio
async def test_entry_planning_limit_order_moderate_spread():
    """Moderate spread (0.1% - 0.5%) should produce a LIMIT at mid price."""
    skill = EntryPlanningSkill()
    ctx = _make_context(
        upstream_results={
            "position_sizing": _position_sizing_result(),
            "market_context": _market_context_result(
                spread_class="moderate",
                spread_pct="0.003",
                bid="49900",
                ask="50100",
                mid="50000",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    plans = result.output["order_plans"]
    assert len(plans) == 1
    assert plans[0]["order_type"] == "LIMIT"
    assert plans[0]["price"] is not None
    assert Decimal(plans[0]["price"]) == Decimal("50000.00")


@pytest.mark.asyncio
async def test_entry_planning_staged_on_wide_spread():
    """Wide spread (>=0.5%) should produce staged entry (3 tranches)."""
    skill = EntryPlanningSkill()
    ctx = _make_context(
        upstream_results={
            "position_sizing": _position_sizing_result(),
            "market_context": _market_context_result(
                spread_class="wide",
                spread_pct="0.02",
                bid="49500",
                ask="50500",
                mid="50000",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    plans = result.output["order_plans"]
    assert len(plans) == 3
    for plan in plans:
        assert plan["order_type"] == "LIMIT"
        assert plan["symbol"] == "BTCUSDT"
        assert plan["side"] == "BUY"
        assert plan["price"] is not None

    # Prices should be ascending (bid toward mid).
    prices = [Decimal(p["price"]) for p in plans]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_entry_planning_no_allocations():
    """Empty allocations should produce no order plans."""
    skill = EntryPlanningSkill()
    ctx = _make_context(
        upstream_results={
            "position_sizing": _position_sizing_result(no_alloc=True),
            "market_context": _market_context_result(),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["order_plans"] == []
    assert "no allocations" in result.message.lower()


@pytest.mark.asyncio
async def test_entry_planning_staged_quantities_sum():
    """Staged tranche quantities should sum to the total allocation quantity."""
    skill = EntryPlanningSkill()
    quantity = "0.03000000"
    ctx = _make_context(
        upstream_results={
            "position_sizing": _position_sizing_result(quantity=quantity),
            "market_context": _market_context_result(
                spread_class="wide",
                spread_pct="0.02",
                bid="49500",
                ask="50500",
                mid="50000",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    plans = result.output["order_plans"]
    total_qty = sum(Decimal(p["quantity"]) for p in plans)
    assert total_qty == Decimal(quantity)


# ===========================================================================
# 6. RiskPrecheckSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_risk_precheck_all_pass():
    """When all checks pass, result should be SUCCESS with allowed orders."""
    skill = RiskPrecheckSkill()
    ctx = _make_context(
        upstream_results={
            "entry_planning": _entry_planning_result(
                quantity="0.01000000",
            ),
        },
        risk_state={"kill_switch_active": False},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    checked = result.output["checked_orders"]
    assert len(checked) == 1
    assert checked[0]["allowed"] is True
    assert checked[0]["violations"] == []
    assert result.output["allowed_count"] == 1
    assert result.output["denied_count"] == 0


@pytest.mark.asyncio
async def test_risk_precheck_kill_switch_active():
    """Active kill switch should deny all orders and return FAILURE."""
    skill = RiskPrecheckSkill()
    ctx = _make_context(
        upstream_results={
            "entry_planning": _entry_planning_result(),
        },
        risk_state={"kill_switch_active": True},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.FAILURE
    assert "denied" in result.message.lower()


@pytest.mark.asyncio
async def test_risk_precheck_notional_exceeded():
    """Order notional exceeding MAX_ORDER_NOTIONAL should be denied."""
    skill = RiskPrecheckSkill()
    # Use a large quantity so notional = 1.0 * 50000 = 50000 > MAX_ORDER_NOTIONAL (10000)
    ctx = _make_context(
        upstream_results={
            "entry_planning": _entry_planning_result(
                quantity="1.00000000",
            ),
        },
        settings={
            "MAX_ORDER_NOTIONAL": "10000",
            "MAX_POSITION_NOTIONAL": "50000",
            "SYMBOL_WHITELIST": ["BTCUSDT", "ETHUSDT"],
        },
        risk_state={"kill_switch_active": False},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.FAILURE
    assert "denied" in result.message.lower()


@pytest.mark.asyncio
async def test_risk_precheck_symbol_not_whitelisted():
    """Order for a symbol not in the whitelist should be denied."""
    skill = RiskPrecheckSkill()
    plan = _entry_planning_result(symbol="DOGEUSDT", quantity="0.01000000")
    ctx = _make_context(
        symbols=["DOGEUSDT"],
        market_data={
            "DOGEUSDT": {
                "last_price": "0.1",
                "bid_price": "0.099",
                "ask_price": "0.101",
                "volume_24h": "1000000",
            },
        },
        upstream_results={
            "entry_planning": plan,
        },
        settings={
            "MAX_ORDER_NOTIONAL": "10000",
            "MAX_POSITION_NOTIONAL": "50000",
            "SYMBOL_WHITELIST": ["BTCUSDT", "ETHUSDT"],
        },
        risk_state={"kill_switch_active": False},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.FAILURE
    # Should contain a whitelist-related violation.
    found_whitelist_violation = False
    for order in result.details.get("checked_orders", []):
        for v in order.get("violations", []):
            if "not_whitelisted" in v:
                found_whitelist_violation = True
    assert found_whitelist_violation


@pytest.mark.asyncio
async def test_risk_precheck_no_orders():
    """No order plans should produce SUCCESS with empty checked list."""
    skill = RiskPrecheckSkill()
    empty_entry = SkillResult(
        skill_id="entry_planning",
        status=SkillStatus.SUCCESS,
        output={"order_plans": [], "num_orders": 0},
        message="No plans.",
    )
    ctx = _make_context(
        upstream_results={"entry_planning": empty_entry},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["checked_orders"] == []


@pytest.mark.asyncio
async def test_risk_precheck_position_limit_exceeded():
    """Exceeding MAX_POSITION_NOTIONAL with existing position should be denied."""
    skill = RiskPrecheckSkill()
    # Existing position notional = 45000, new order notional ~500 from 0.01 * 50000 = 500
    # So projected = 45500 which is < 50000 (passes). Let's make it fail:
    # existing = 49600, new = 0.01 * 50000 = 500 -> projected = 50100 > 50000
    ctx = _make_context(
        upstream_results={
            "entry_planning": _entry_planning_result(quantity="0.01000000"),
        },
        current_positions={
            "BTCUSDT": {"notional": "49600"},
        },
        settings={
            "MAX_ORDER_NOTIONAL": "100000",
            "MAX_POSITION_NOTIONAL": "50000",
            "SYMBOL_WHITELIST": ["BTCUSDT"],
        },
        risk_state={"kill_switch_active": False},
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.FAILURE
    found_position_violation = False
    for order in result.details.get("checked_orders", []):
        for v in order.get("violations", []):
            if "position_limit_exceeded" in v:
                found_position_violation = True
    assert found_position_violation


def test_risk_precheck_properties():
    """RiskPrecheckSkill should declare CRITICAL risk level."""
    from app.agents.types import SkillRiskLevel
    skill = RiskPrecheckSkill()
    assert skill.risk_level == SkillRiskLevel.CRITICAL
    assert "entry_planning" in skill.prerequisites


# ===========================================================================
# 7. TradeDecisionSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_trade_decision_trade():
    """When risk precheck passes, decision should be TRADE."""
    skill = TradeDecisionSkill()
    ctx = _make_context(
        upstream_results={
            "opportunity_scoring": _opportunity_scoring_result(score=75.0),
            "risk_precheck": _risk_precheck_result(allowed=True),
            "position_sizing": _position_sizing_result(),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["decision"] == "TRADE"
    assert len(result.output["selected_orders"]) > 0
    assert result.output["confidence"] > 0


@pytest.mark.asyncio
async def test_trade_decision_no_trade_risk_failure():
    """When risk precheck fails, decision should be NO_TRADE."""
    skill = TradeDecisionSkill()
    ctx = _make_context(
        upstream_results={
            "opportunity_scoring": _opportunity_scoring_result(score=75.0),
            "risk_precheck": _risk_precheck_result(allowed=False),
            "position_sizing": _position_sizing_result(),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["decision"] == "NO_TRADE"
    assert result.output["selected_orders"] == []
    assert "risk precheck" in result.output["reasoning_summary"].lower()


@pytest.mark.asyncio
async def test_trade_decision_no_trade_low_scores():
    """When opportunity scoring flags no_trade, decision should be NO_TRADE."""
    skill = TradeDecisionSkill()
    ctx = _make_context(
        upstream_results={
            "opportunity_scoring": _opportunity_scoring_result(
                score=10.0, no_trade=True,
            ),
            "risk_precheck": _risk_precheck_result(allowed=True),
            "position_sizing": _position_sizing_result(),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["decision"] == "NO_TRADE"
    assert "threshold" in result.output["reasoning_summary"].lower()


@pytest.mark.asyncio
async def test_trade_decision_no_trade_empty_allocations():
    """When position sizing has no allocations, decision should be NO_TRADE."""
    skill = TradeDecisionSkill()
    ctx = _make_context(
        upstream_results={
            "opportunity_scoring": _opportunity_scoring_result(score=75.0),
            "risk_precheck": _risk_precheck_result(allowed=True),
            "position_sizing": _position_sizing_result(no_alloc=True),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["decision"] == "NO_TRADE"


@pytest.mark.asyncio
async def test_trade_decision_confidence_range():
    """Confidence should always be in [0, 1]."""
    skill = TradeDecisionSkill()
    ctx = _make_context(
        upstream_results={
            "opportunity_scoring": _opportunity_scoring_result(score=100.0),
            "risk_precheck": _risk_precheck_result(allowed=True),
            "position_sizing": _position_sizing_result(),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    conf = result.output["confidence"]
    assert 0.0 <= conf <= 1.0


# ===========================================================================
# 8. NoTradeJustificationSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_no_trade_justification_skip_on_trade():
    """Should return SKIPPED when the decision was TRADE."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="TRADE"),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SKIPPED
    assert "trade" in result.message.lower()


@pytest.mark.asyncio
async def test_no_trade_justification_on_no_trade():
    """Should produce justification when the decision was NO_TRADE."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
            "opportunity_scoring": _opportunity_scoring_result(
                score=10.0, no_trade=True,
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert "reasons" in result.output
    assert "blocked_symbols" in result.output
    assert "limiting_factors" in result.output
    assert "next_review_suggestion" in result.output


@pytest.mark.asyncio
async def test_no_trade_justification_includes_risk_violations():
    """Justification should include risk precheck violations."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
            "risk_precheck": _risk_precheck_result(allowed=False),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    # Should include limiting factors from risk precheck.
    factors = result.output["limiting_factors"]
    assert len(factors) > 0
    found_kill_switch = any("kill_switch" in f for f in factors)
    assert found_kill_switch


@pytest.mark.asyncio
async def test_no_trade_justification_next_review_kill_switch():
    """Kill switch violation should suggest reviewing after manual clear."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
            "risk_precheck": _risk_precheck_result(allowed=False),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert "kill switch" in result.output["next_review_suggestion"].lower()


@pytest.mark.asyncio
async def test_no_trade_justification_next_review_low_scores():
    """Low scores should suggest reviewing in 15 minutes."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
            "opportunity_scoring": _opportunity_scoring_result(
                score=10.0, no_trade=True,
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert "15 minutes" in result.output["next_review_suggestion"]


@pytest.mark.asyncio
async def test_no_trade_justification_low_liquidity():
    """Low liquidity from market context should appear as a limiting factor."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
            "market_context": _market_context_result(
                low_liquidity=True,
                volume="1000",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    factors = result.output["limiting_factors"]
    found_liquidity = any("liquidity" in f.lower() for f in factors)
    assert found_liquidity
    assert "1 hour" in result.output["next_review_suggestion"]


# ===========================================================================
# 9. ExecutionReviewSkill
# ===========================================================================


@pytest.mark.asyncio
async def test_execution_review_pending_no_data():
    """Without execution data, should return pending review."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        settings={},  # No execution_outcomes key
        upstream_results={
            "trade_decision": _trade_decision_result(decision="TRADE"),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["status"] == "pending_review"
    assert result.output["fill_quality"] == "pending"
    assert len(result.output["deviation_notes"]) > 0


@pytest.mark.asyncio
async def test_execution_review_completed_with_slippage():
    """With execution data, should compute slippage and fill quality."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        settings={
            "execution_outcomes": [
                {
                    "symbol": "BTCUSDT",
                    "fill_price": "50010",
                    "fill_quantity": "0.01000000",
                },
            ],
        },
        upstream_results={
            "trade_decision": SkillResult(
                skill_id="trade_decision",
                status=SkillStatus.SUCCESS,
                output={
                    "decision": "TRADE",
                    "selected_orders": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "BUY",
                            "order_type": "LIMIT",
                            "price": "50000",
                            "quantity": "0.01000000",
                            "allowed": True,
                            "violations": [],
                            "estimated_notional": "500",
                        },
                    ],
                    "confidence": 0.75,
                    "reasoning_summary": "ok",
                },
                message="TRADE.",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["status"] == "reviewed"
    assert result.output["fill_quality"] in (
        "excellent", "good", "acceptable", "poor", "unknown",
    )
    slippage = result.output["slippage_summary"]
    assert "entries" in slippage
    assert len(slippage["entries"]) == 1
    entry = slippage["entries"][0]
    assert entry["symbol"] == "BTCUSDT"
    assert Decimal(entry["fill_price"]) == Decimal("50010")
    assert Decimal(entry["planned_price"]) == Decimal("50000")
    # slippage = (50010 - 50000) / 50000 = 0.0002 -> excellent (<0.001)
    assert result.output["fill_quality"] == "excellent"


@pytest.mark.asyncio
async def test_execution_review_skip_on_no_trade():
    """Should skip when trade_decision was NO_TRADE."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        upstream_results={
            "trade_decision": _trade_decision_result(decision="NO_TRADE"),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SKIPPED
    assert "no_trade" in result.message.lower()


@pytest.mark.asyncio
async def test_execution_review_quantity_deviation():
    """Partial fill should be noted as a deviation."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        settings={
            "execution_outcomes": [
                {
                    "symbol": "BTCUSDT",
                    "fill_price": "50000",
                    "fill_quantity": "0.00800000",  # Partial fill
                },
            ],
        },
        upstream_results={
            "trade_decision": SkillResult(
                skill_id="trade_decision",
                status=SkillStatus.SUCCESS,
                output={
                    "decision": "TRADE",
                    "selected_orders": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "BUY",
                            "order_type": "MARKET",
                            "price": None,
                            "quantity": "0.01000000",
                            "allowed": True,
                            "violations": [],
                            "estimated_notional": "500",
                        },
                    ],
                    "confidence": 0.75,
                    "reasoning_summary": "ok",
                },
                message="TRADE.",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["status"] == "reviewed"
    assert len(result.output["deviation_notes"]) > 0
    assert any("quantity deviation" in n for n in result.output["deviation_notes"])


@pytest.mark.asyncio
async def test_execution_review_poor_fill_quality():
    """Large slippage (>1%) should classify as poor fill quality."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        settings={
            "execution_outcomes": [
                {
                    "symbol": "BTCUSDT",
                    "fill_price": "50600",  # 1.2% slippage
                    "fill_quantity": "0.01000000",
                },
            ],
        },
        upstream_results={
            "trade_decision": SkillResult(
                skill_id="trade_decision",
                status=SkillStatus.SUCCESS,
                output={
                    "decision": "TRADE",
                    "selected_orders": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "BUY",
                            "order_type": "LIMIT",
                            "price": "50000",
                            "quantity": "0.01000000",
                            "allowed": True,
                            "violations": [],
                            "estimated_notional": "500",
                        },
                    ],
                    "confidence": 0.75,
                    "reasoning_summary": "ok",
                },
                message="TRADE.",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert result.output["fill_quality"] == "poor"


@pytest.mark.asyncio
async def test_execution_review_unexpected_fill():
    """A fill for a symbol not in selected_orders should produce a deviation note."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(
        settings={
            "execution_outcomes": [
                {
                    "symbol": "ETHUSDT",
                    "fill_price": "3000",
                    "fill_quantity": "1.0",
                },
            ],
        },
        upstream_results={
            "trade_decision": SkillResult(
                skill_id="trade_decision",
                status=SkillStatus.SUCCESS,
                output={
                    "decision": "TRADE",
                    "selected_orders": [
                        {
                            "symbol": "BTCUSDT",
                            "side": "BUY",
                            "order_type": "MARKET",
                            "price": None,
                            "quantity": "0.01000000",
                            "allowed": True,
                            "violations": [],
                            "estimated_notional": "500",
                        },
                    ],
                    "confidence": 0.75,
                    "reasoning_summary": "ok",
                },
                message="TRADE.",
            ),
        },
    )
    result = await skill.execute(ctx)

    assert result.status == SkillStatus.SUCCESS
    assert any(
        "unexpected fill" in n.lower() for n in result.output["deviation_notes"]
    )


# ===========================================================================
# Cross-cutting: can_run / prerequisite validation
# ===========================================================================


def test_opportunity_scoring_can_run_without_prerequisite():
    """OpportunityScoringSkill should fail can_run without market_context upstream."""
    skill = OpportunityScoringSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "market_context" in reason


def test_position_sizing_can_run_without_prerequisites():
    """PositionSizingSkill should fail can_run without both prerequisites."""
    skill = PositionSizingSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok


def test_entry_planning_can_run_without_prerequisite():
    """EntryPlanningSkill should fail can_run without position_sizing."""
    skill = EntryPlanningSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "position_sizing" in reason


def test_risk_precheck_can_run_without_prerequisite():
    """RiskPrecheckSkill should fail can_run without entry_planning."""
    skill = RiskPrecheckSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "entry_planning" in reason


def test_trade_decision_can_run_without_prerequisite():
    """TradeDecisionSkill should fail can_run without risk_precheck."""
    skill = TradeDecisionSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "risk_precheck" in reason


def test_no_trade_justification_can_run_without_prerequisite():
    """NoTradeJustificationSkill should fail can_run without trade_decision."""
    skill = NoTradeJustificationSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "trade_decision" in reason


def test_execution_review_can_run_without_prerequisite():
    """ExecutionReviewSkill should fail can_run without trade_decision."""
    skill = ExecutionReviewSkill()
    ctx = _make_context(upstream_results={})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "trade_decision" in reason


def test_can_run_wrong_trading_mode():
    """Skills should fail can_run when trading mode is not in allowed_modes."""
    skill = BudgetInterpretationSkill()
    ctx = _make_context(trading_mode="BACKTEST")
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "BACKTEST" in reason


def test_can_run_prerequisite_non_success():
    """Prerequisite with non-SUCCESS status should block can_run."""
    skill = OpportunityScoringSkill()
    failed_market = SkillResult(
        skill_id="market_context",
        status=SkillStatus.FAILURE,
        message="failed",
    )
    ctx = _make_context(upstream_results={"market_context": failed_market})
    ok, reason = skill.can_run(ctx)
    assert not ok
    assert "did not succeed" in reason.lower()

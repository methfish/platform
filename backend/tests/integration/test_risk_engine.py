"""
Integration tests for the RiskEngine.

Tests the risk engine's orchestration of multiple risk checks including
short-circuit behavior, run-all mode, check registration/removal,
exception handling, and warning collection.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import uuid4

import pytest

from app.core.enums import RiskCheckResult
from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse
from app.risk.checks.daily_loss import DailyLossCheck
from app.risk.checks.kill_switch import KillSwitchCheck
from app.risk.checks.order_rate import OrderRateCheck
from app.risk.checks.order_size import OrderSizeCheck
from app.risk.checks.symbol_whitelist import SymbolWhitelistCheck
from app.risk.engine import RiskEngine, RiskEngineResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order_mock(**overrides):
    """Create a mock Order with sensible defaults for testing."""
    order = MagicMock()
    order.id = overrides.get("id", uuid4())
    order.client_order_id = overrides.get("client_order_id", "test-123")
    order.symbol = overrides.get("symbol", "BTCUSDT")
    order.side = overrides.get("side", "BUY")
    order.order_type = overrides.get("order_type", "LIMIT")
    order.quantity = overrides.get("quantity", Decimal("0.1"))
    order.price = overrides.get("price", Decimal("50000"))
    order.strategy_id = overrides.get("strategy_id", None)
    order.exchange = overrides.get("exchange", "paper")
    order.trading_mode = overrides.get("trading_mode", "PAPER")
    return order


def _make_passing_context(**overrides):
    """Create a RiskCheckContext that should pass all standard checks."""
    defaults = dict(
        order_id=str(uuid4()),
        client_order_id="test-123",
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=Decimal("0.1"),
        price=Decimal("50000"),
        last_price=Decimal("50000"),
        bid_price=Decimal("49999"),
        ask_price=Decimal("50001"),
        kill_switch_active=False,
        trading_mode="PAPER",
        exchange="paper",
        daily_realized_pnl=Decimal("0"),
        orders_in_last_minute=0,
        settings={
            "MAX_ORDER_QUANTITY": Decimal("100"),
            "MAX_ORDER_NOTIONAL": Decimal("1000000"),
            "MAX_DAILY_LOSS": Decimal("5000"),
            "MAX_ORDERS_PER_MINUTE": 30,
            "SYMBOL_WHITELIST": {"BTCUSDT", "ETHUSDT", "SOLUSDT"},
        },
    )
    defaults.update(overrides)
    return RiskCheckContext(**defaults)


class _ExplodingCheck(BaseRiskCheck):
    """A check that always raises an exception (for testing error handling)."""

    @property
    def name(self) -> str:
        return "exploding_check"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        raise RuntimeError("Boom! Something went wrong inside the check.")


class _AlwaysWarnCheck(BaseRiskCheck):
    """A check that always returns WARN."""

    @property
    def name(self) -> str:
        return "always_warn"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        return self._warn("This is a warning.")


class _TrackingCheck(BaseRiskCheck):
    """A check that records whether it was called (for short-circuit tests)."""

    def __init__(self):
        self.was_called = False

    @property
    def name(self) -> str:
        return "tracking_check"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        self.was_called = True
        return self._pass("Tracking check passed.")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_no_checks_returns_passed():
    """An engine with zero registered checks should return passed=True."""
    engine = RiskEngine(checks=[])
    order = _make_order_mock()
    ctx = _make_passing_context()

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is True
    assert result.results == []
    assert result.failed_checks == []
    assert result.warned_checks == []


@pytest.mark.asyncio
async def test_engine_all_checks_pass():
    """Engine passes when all registered checks pass with valid context."""
    engine = RiskEngine(checks=[
        KillSwitchCheck(),
        OrderSizeCheck(),
        DailyLossCheck(),
        SymbolWhitelistCheck(),
        OrderRateCheck(),
    ])
    order = _make_order_mock()
    ctx = _make_passing_context()

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is True
    assert len(result.results) == 5
    assert result.failed_checks == []
    assert all(r.result == RiskCheckResult.PASS for r in result.results)


@pytest.mark.asyncio
async def test_engine_fails_on_kill_switch():
    """Engine fails when the kill switch is active."""
    engine = RiskEngine(checks=[
        KillSwitchCheck(),
        OrderSizeCheck(),
    ])
    order = _make_order_mock()
    ctx = _make_passing_context(kill_switch_active=True)

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "kill_switch" in result.failed_checks


@pytest.mark.asyncio
async def test_short_circuit_stops_on_first_fail():
    """In default (short-circuit) mode, engine stops after the first FAIL."""
    tracker = _TrackingCheck()

    engine = RiskEngine(checks=[
        KillSwitchCheck(),  # will FAIL
        tracker,            # should NOT be called
    ])
    order = _make_order_mock()
    ctx = _make_passing_context(kill_switch_active=True)

    result = await engine.evaluate_order(order, context=ctx, run_all=False)

    assert result.passed is False
    assert len(result.results) == 1
    assert result.results[0].check_name == "kill_switch"
    assert tracker.was_called is False


@pytest.mark.asyncio
async def test_run_all_continues_after_fail():
    """In run_all mode, engine runs all checks even after a FAIL."""
    tracker = _TrackingCheck()

    engine = RiskEngine(checks=[
        KillSwitchCheck(),  # will FAIL
        tracker,            # SHOULD be called
    ])
    order = _make_order_mock()
    ctx = _make_passing_context(kill_switch_active=True)

    result = await engine.evaluate_order(order, context=ctx, run_all=True)

    assert result.passed is False
    assert len(result.results) == 2
    assert tracker.was_called is True
    assert "kill_switch" in result.failed_checks


@pytest.mark.asyncio
async def test_register_check():
    """register_check adds a new check to the engine."""
    engine = RiskEngine(checks=[])
    assert len(engine.checks) == 0

    engine.register_check(KillSwitchCheck())
    assert len(engine.checks) == 1
    assert engine.checks[0].name == "kill_switch"

    engine.register_check(OrderSizeCheck())
    assert len(engine.checks) == 2
    assert engine.checks[1].name == "order_size"


@pytest.mark.asyncio
async def test_remove_check():
    """remove_check removes a check by its canonical name."""
    engine = RiskEngine(checks=[
        KillSwitchCheck(),
        OrderSizeCheck(),
        DailyLossCheck(),
    ])
    assert len(engine.checks) == 3

    engine.remove_check("order_size")
    assert len(engine.checks) == 2
    check_names = [c.name for c in engine.checks]
    assert "order_size" not in check_names
    assert "kill_switch" in check_names
    assert "daily_loss" in check_names


@pytest.mark.asyncio
async def test_exception_in_check_results_in_fail():
    """A check that raises an exception should result in FAIL, not a crash."""
    engine = RiskEngine(checks=[
        _ExplodingCheck(),
    ])
    order = _make_order_mock()
    ctx = _make_passing_context()

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "exploding_check" in result.failed_checks
    assert len(result.results) == 1
    assert result.results[0].result == RiskCheckResult.FAIL
    assert "exception" in result.results[0].message.lower()


@pytest.mark.asyncio
async def test_warned_checks_collected():
    """Checks returning WARN should be collected in warned_checks."""
    engine = RiskEngine(checks=[
        KillSwitchCheck(),
        _AlwaysWarnCheck(),
        OrderSizeCheck(),
    ])
    order = _make_order_mock()
    ctx = _make_passing_context()

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is True
    assert "always_warn" in result.warned_checks
    assert result.failed_checks == []


@pytest.mark.asyncio
async def test_daily_loss_warn_at_threshold():
    """DailyLossCheck should WARN when approaching the max daily loss (80%)."""
    engine = RiskEngine(checks=[DailyLossCheck()])
    order = _make_order_mock()

    # 80% of 5000 = 4000. A loss of -4100 should trigger WARN.
    ctx = _make_passing_context(
        daily_realized_pnl=Decimal("-4100"),
        settings={"MAX_DAILY_LOSS": Decimal("5000")},
    )

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is True
    assert "daily_loss" in result.warned_checks


@pytest.mark.asyncio
async def test_daily_loss_fail_at_limit():
    """DailyLossCheck should FAIL when daily loss reaches the max."""
    engine = RiskEngine(checks=[DailyLossCheck()])
    order = _make_order_mock()

    ctx = _make_passing_context(
        daily_realized_pnl=Decimal("-5000"),
        settings={"MAX_DAILY_LOSS": Decimal("5000")},
    )

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "daily_loss" in result.failed_checks


@pytest.mark.asyncio
async def test_order_size_fail_on_quantity():
    """OrderSizeCheck should FAIL when quantity exceeds the maximum."""
    engine = RiskEngine(checks=[OrderSizeCheck()])
    order = _make_order_mock()

    ctx = _make_passing_context(
        quantity=Decimal("200"),
        settings={"MAX_ORDER_QUANTITY": Decimal("100"), "MAX_ORDER_NOTIONAL": Decimal("99999999")},
    )

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "order_size" in result.failed_checks


@pytest.mark.asyncio
async def test_symbol_whitelist_fail_on_unlisted_symbol():
    """SymbolWhitelistCheck should FAIL when symbol is not in the whitelist."""
    engine = RiskEngine(checks=[SymbolWhitelistCheck()])
    order = _make_order_mock()

    ctx = _make_passing_context(
        symbol="DOGEUSDT",
        settings={"SYMBOL_WHITELIST": {"BTCUSDT", "ETHUSDT"}},
    )

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "symbol_whitelist" in result.failed_checks


@pytest.mark.asyncio
async def test_order_rate_fail():
    """OrderRateCheck should FAIL when order rate exceeds the limit."""
    engine = RiskEngine(checks=[OrderRateCheck()])
    order = _make_order_mock()

    ctx = _make_passing_context(
        orders_in_last_minute=31,
        settings={"MAX_ORDERS_PER_MINUTE": 30},
    )

    result = await engine.evaluate_order(order, context=ctx)

    assert result.passed is False
    assert "order_rate" in result.failed_checks


@pytest.mark.asyncio
async def test_context_built_from_order_when_none_provided():
    """When context=None, the engine should build one from the order."""
    engine = RiskEngine(checks=[KillSwitchCheck()])
    order = _make_order_mock(symbol="BTCUSDT", side="BUY")

    # No context passed -- engine builds from order mock
    result = await engine.evaluate_order(order, context=None)

    assert result.passed is True
    assert len(result.results) == 1
    assert result.results[0].check_name == "kill_switch"


@pytest.mark.asyncio
async def test_remove_nonexistent_check_is_noop():
    """Removing a check name that does not exist should be a no-op."""
    engine = RiskEngine(checks=[KillSwitchCheck()])
    assert len(engine.checks) == 1

    engine.remove_check("nonexistent_check")
    assert len(engine.checks) == 1


@pytest.mark.asyncio
async def test_multiple_failures_collected_in_run_all():
    """In run_all mode, all failures should be collected in failed_checks."""
    engine = RiskEngine(checks=[
        KillSwitchCheck(),
        OrderSizeCheck(),
        OrderRateCheck(),
    ])
    order = _make_order_mock()

    # Context that triggers failures in kill_switch and order_rate
    ctx = _make_passing_context(
        kill_switch_active=True,
        orders_in_last_minute=100,
        settings={"MAX_ORDERS_PER_MINUTE": 30, "MAX_ORDER_QUANTITY": Decimal("100"), "MAX_ORDER_NOTIONAL": Decimal("99999999")},
    )

    result = await engine.evaluate_order(order, context=ctx, run_all=True)

    assert result.passed is False
    assert "kill_switch" in result.failed_checks
    assert "order_rate" in result.failed_checks
    assert len(result.results) == 3

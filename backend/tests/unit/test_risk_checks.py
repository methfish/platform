"""
Unit tests for individual risk checks.

Each check receives a RiskCheckContext and returns a RiskCheckResponse.
Tests cover PASS, FAIL, WARN, and SKIP outcomes for every check.
"""

import pytest
from decimal import Decimal

from app.core.enums import RiskCheckResult
from app.risk.checks.base import RiskCheckContext
from app.risk.checks.kill_switch import KillSwitchCheck
from app.risk.checks.order_size import OrderSizeCheck
from app.risk.checks.position_limit import PositionLimitCheck
from app.risk.checks.daily_loss import DailyLossCheck
from app.risk.checks.order_rate import OrderRateCheck
from app.risk.checks.price_deviation import PriceDeviationCheck
from app.risk.checks.symbol_whitelist import SymbolWhitelistCheck


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_context(**overrides) -> RiskCheckContext:
    """Build a RiskCheckContext with sensible defaults for testing."""
    defaults = dict(
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=Decimal("1"),
        price=Decimal("50000"),
        last_price=Decimal("50000"),
        bid_price=Decimal("49999"),
        ask_price=Decimal("50001"),
        mid_price=Decimal("50000"),
        current_position_quantity=Decimal("0"),
        current_position_notional=Decimal("0"),
        current_position_side="FLAT",
        daily_realized_pnl=Decimal("0"),
        orders_in_last_minute=0,
        kill_switch_active=False,
        settings={
            "MAX_ORDER_QUANTITY": Decimal("100"),
            "MAX_ORDER_NOTIONAL": Decimal("10000000"),
            "MAX_POSITION_NOTIONAL": Decimal("50000"),
            "MAX_DAILY_LOSS": Decimal("5000"),
            "PRICE_DEVIATION_THRESHOLD": Decimal("0.05"),
            "MAX_ORDERS_PER_MINUTE": 30,
            "SYMBOL_WHITELIST": "BTCUSDT,ETHUSDT",
        },
    )
    defaults.update(overrides)
    return RiskCheckContext(**defaults)


# ---------------------------------------------------------------------------
# KillSwitchCheck
# ---------------------------------------------------------------------------

class TestKillSwitchCheck:
    """Test the global kill switch risk check."""

    @pytest.mark.asyncio
    async def test_fail_when_kill_switch_active(self):
        ctx = _base_context(kill_switch_active=True)
        check = KillSwitchCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL
        assert response.check_name == "kill_switch"

    @pytest.mark.asyncio
    async def test_pass_when_kill_switch_inactive(self):
        ctx = _base_context(kill_switch_active=False)
        check = KillSwitchCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS


# ---------------------------------------------------------------------------
# OrderSizeCheck
# ---------------------------------------------------------------------------

class TestOrderSizeCheck:
    """Test order quantity and notional size limits."""

    @pytest.mark.asyncio
    async def test_pass_within_limits(self):
        ctx = _base_context(
            quantity=Decimal("10"),
            price=Decimal("100"),
            settings={
                "MAX_ORDER_QUANTITY": Decimal("100"),
                "MAX_ORDER_NOTIONAL": Decimal("100000"),
            },
        )
        check = OrderSizeCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_quantity_exceeds_max(self):
        ctx = _base_context(
            quantity=Decimal("150"),
            price=Decimal("100"),
            settings={
                "MAX_ORDER_QUANTITY": Decimal("100"),
                "MAX_ORDER_NOTIONAL": Decimal("100000"),
            },
        )
        check = OrderSizeCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL
        assert "quantity" in response.message.lower()

    @pytest.mark.asyncio
    async def test_fail_notional_exceeds_max(self):
        ctx = _base_context(
            quantity=Decimal("10"),
            price=Decimal("50000"),
            settings={
                "MAX_ORDER_QUANTITY": Decimal("100"),
                "MAX_ORDER_NOTIONAL": Decimal("10000"),
            },
        )
        check = OrderSizeCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL
        assert "notional" in response.message.lower()

    @pytest.mark.asyncio
    async def test_pass_at_exact_quantity_limit(self):
        ctx = _base_context(
            quantity=Decimal("100"),
            price=Decimal("1"),
            settings={
                "MAX_ORDER_QUANTITY": Decimal("100"),
                "MAX_ORDER_NOTIONAL": Decimal("100000"),
            },
        )
        check = OrderSizeCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS


# ---------------------------------------------------------------------------
# PositionLimitCheck
# ---------------------------------------------------------------------------

class TestPositionLimitCheck:
    """Test that resulting position notional is kept within limits."""

    @pytest.mark.asyncio
    async def test_pass_within_limits(self):
        ctx = _base_context(
            side="BUY",
            quantity=Decimal("1"),
            price=Decimal("10000"),
            current_position_notional=Decimal("0"),
            current_position_side="FLAT",
            settings={"MAX_POSITION_NOTIONAL": Decimal("50000")},
        )
        check = PositionLimitCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_exceeds_max_position_notional(self):
        ctx = _base_context(
            side="BUY",
            quantity=Decimal("5"),
            price=Decimal("20000"),
            current_position_notional=Decimal("40000"),
            current_position_side="LONG",
            settings={"MAX_POSITION_NOTIONAL": Decimal("50000")},
        )
        check = PositionLimitCheck()
        response = await check.evaluate(ctx)
        # Resulting notional: 40000 + (5 * 20000) = 140000 > 50000
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_pass_sell_reducing_long_position(self):
        ctx = _base_context(
            side="SELL",
            quantity=Decimal("1"),
            price=Decimal("10000"),
            current_position_notional=Decimal("30000"),
            current_position_side="LONG",
            settings={"MAX_POSITION_NOTIONAL": Decimal("50000")},
        )
        check = PositionLimitCheck()
        response = await check.evaluate(ctx)
        # Reducing long: abs(30000 - 10000) = 20000 < 50000
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_skip_when_no_price_available(self):
        ctx = _base_context(
            price=None,
            last_price=None,
            settings={"MAX_POSITION_NOTIONAL": Decimal("50000")},
        )
        check = PositionLimitCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.SKIP


# ---------------------------------------------------------------------------
# DailyLossCheck
# ---------------------------------------------------------------------------

class TestDailyLossCheck:
    """Test daily realized PnL circuit breaker."""

    @pytest.mark.asyncio
    async def test_pass_within_limits(self):
        ctx = _base_context(
            daily_realized_pnl=Decimal("-1000"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_pass_with_positive_pnl(self):
        ctx = _base_context(
            daily_realized_pnl=Decimal("2000"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_when_loss_reaches_max(self):
        ctx = _base_context(
            daily_realized_pnl=Decimal("-5000"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_fail_when_loss_exceeds_max(self):
        ctx = _base_context(
            daily_realized_pnl=Decimal("-7500"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_warn_at_80_percent_threshold(self):
        # 80% of 5000 = 4000
        ctx = _base_context(
            daily_realized_pnl=Decimal("-4000"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.WARN

    @pytest.mark.asyncio
    async def test_pass_just_below_warn_threshold(self):
        # Just below 80% of 5000 = 3999
        ctx = _base_context(
            daily_realized_pnl=Decimal("-3999"),
            settings={"MAX_DAILY_LOSS": Decimal("5000")},
        )
        check = DailyLossCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS


# ---------------------------------------------------------------------------
# OrderRateCheck
# ---------------------------------------------------------------------------

class TestOrderRateCheck:
    """Test order submission rate limiter."""

    @pytest.mark.asyncio
    async def test_pass_within_limits(self):
        ctx = _base_context(
            orders_in_last_minute=5,
            settings={"MAX_ORDERS_PER_MINUTE": 30},
        )
        check = OrderRateCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_when_rate_equals_max(self):
        ctx = _base_context(
            orders_in_last_minute=30,
            settings={"MAX_ORDERS_PER_MINUTE": 30},
        )
        check = OrderRateCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_fail_when_rate_exceeds_max(self):
        ctx = _base_context(
            orders_in_last_minute=50,
            settings={"MAX_ORDERS_PER_MINUTE": 30},
        )
        check = OrderRateCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_warn_at_80_percent_threshold(self):
        # 80% of 30 = 24
        ctx = _base_context(
            orders_in_last_minute=24,
            settings={"MAX_ORDERS_PER_MINUTE": 30},
        )
        check = OrderRateCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.WARN

    @pytest.mark.asyncio
    async def test_pass_just_below_warn_threshold(self):
        # 80% of 30 = 24, so 23 should pass
        ctx = _base_context(
            orders_in_last_minute=23,
            settings={"MAX_ORDERS_PER_MINUTE": 30},
        )
        check = OrderRateCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS


# ---------------------------------------------------------------------------
# PriceDeviationCheck
# ---------------------------------------------------------------------------

class TestPriceDeviationCheck:
    """Test limit price deviation from market (fat-finger guard)."""

    @pytest.mark.asyncio
    async def test_pass_within_threshold(self):
        ctx = _base_context(
            price=Decimal("50500"),          # 1% above reference
            mid_price=Decimal("50000"),
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_exceeds_threshold(self):
        ctx = _base_context(
            price=Decimal("60000"),          # 20% above reference
            mid_price=Decimal("50000"),
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_fail_below_threshold(self):
        ctx = _base_context(
            price=Decimal("40000"),          # 20% below reference
            mid_price=Decimal("50000"),
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_skip_for_market_order_no_price(self):
        ctx = _base_context(
            price=None,
            order_type="MARKET",
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.SKIP

    @pytest.mark.asyncio
    async def test_skip_when_no_reference_price(self):
        ctx = _base_context(
            price=Decimal("50000"),
            mid_price=None,
            last_price=None,
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.SKIP

    @pytest.mark.asyncio
    async def test_uses_last_price_when_mid_unavailable(self):
        ctx = _base_context(
            price=Decimal("50500"),
            mid_price=None,
            last_price=Decimal("50000"),
            settings={"PRICE_DEVIATION_THRESHOLD": Decimal("0.05")},
        )
        check = PriceDeviationCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS


# ---------------------------------------------------------------------------
# SymbolWhitelistCheck
# ---------------------------------------------------------------------------

class TestSymbolWhitelistCheck:
    """Test symbol whitelist enforcement."""

    @pytest.mark.asyncio
    async def test_pass_when_symbol_in_whitelist(self):
        ctx = _base_context(
            symbol="BTCUSDT",
            settings={"SYMBOL_WHITELIST": "BTCUSDT,ETHUSDT"},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_when_symbol_not_in_whitelist(self):
        ctx = _base_context(
            symbol="DOGEUSDT",
            settings={"SYMBOL_WHITELIST": "BTCUSDT,ETHUSDT"},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_pass_when_whitelist_is_empty_string(self):
        ctx = _base_context(
            symbol="DOGEUSDT",
            settings={"SYMBOL_WHITELIST": ""},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_pass_when_whitelist_is_empty_set(self):
        ctx = _base_context(
            symbol="DOGEUSDT",
            settings={"SYMBOL_WHITELIST": set()},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_whitelist_is_case_insensitive(self):
        ctx = _base_context(
            symbol="btcusdt",
            settings={"SYMBOL_WHITELIST": "BTCUSDT,ETHUSDT"},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_whitelist_accepts_set_type(self):
        ctx = _base_context(
            symbol="ETHUSDT",
            settings={"SYMBOL_WHITELIST": {"BTCUSDT", "ETHUSDT"}},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

    @pytest.mark.asyncio
    async def test_whitelist_accepts_list_type(self):
        ctx = _base_context(
            symbol="ETHUSDT",
            settings={"SYMBOL_WHITELIST": ["BTCUSDT", "ETHUSDT"]},
        )
        check = SymbolWhitelistCheck()
        response = await check.evaluate(ctx)
        assert response.result == RiskCheckResult.PASS

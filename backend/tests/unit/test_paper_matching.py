"""
Unit tests for the paper trading matching engine.

Tests market and limit order fill simulation, slippage,
commission calculation, and commission asset resolution.
"""

import pytest
from decimal import Decimal

from app.core.enums import OrderSide, OrderType
from app.exchange.paper.matching import MatchingEngine, PaperOrderState, SimulatedFill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _market_order(
    side: OrderSide = OrderSide.BUY,
    quantity: Decimal = Decimal("1"),
    filled_quantity: Decimal = Decimal("0"),
    symbol: str = "BTCUSDT",
) -> PaperOrderState:
    return PaperOrderState(
        exchange_order_id="exch-001",
        client_order_id="client-001",
        symbol=symbol,
        side=side,
        order_type=OrderType.MARKET,
        quantity=quantity,
        price=None,
        filled_quantity=filled_quantity,
    )


def _limit_order(
    side: OrderSide = OrderSide.BUY,
    price: Decimal = Decimal("50000"),
    quantity: Decimal = Decimal("1"),
    filled_quantity: Decimal = Decimal("0"),
    symbol: str = "BTCUSDT",
) -> PaperOrderState:
    return PaperOrderState(
        exchange_order_id="exch-002",
        client_order_id="client-002",
        symbol=symbol,
        side=side,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
        filled_quantity=filled_quantity,
    )


# ---------------------------------------------------------------------------
# Market order fills
# ---------------------------------------------------------------------------

class TestMarketOrderFills:
    """Test market order fill simulation."""

    def test_buy_fills_at_ask_with_slippage(self):
        engine = MatchingEngine(
            commission_rate=Decimal("0.001"),
            slippage_bps=Decimal("0.0005"),
        )
        order = _market_order(side=OrderSide.BUY)
        fill = engine.try_fill_market(
            order,
            last_price=Decimal("50000"),
            bid=Decimal("49999"),
            ask=Decimal("50001"),
        )
        assert fill is not None
        # Expected price: ask * (1 + slippage) = 50001 * 1.0005
        expected_price = Decimal("50001") * Decimal("1.0005")
        assert fill.price == expected_price.quantize(Decimal("0.00000001"))

    def test_buy_fills_at_last_price_when_no_ask(self):
        engine = MatchingEngine(slippage_bps=Decimal("0.0005"))
        order = _market_order(side=OrderSide.BUY)
        fill = engine.try_fill_market(
            order,
            last_price=Decimal("50000"),
            bid=None,
            ask=None,
        )
        assert fill is not None
        expected_price = Decimal("50000") * Decimal("1.0005")
        assert fill.price == expected_price.quantize(Decimal("0.00000001"))

    def test_sell_fills_at_bid_with_slippage(self):
        engine = MatchingEngine(
            commission_rate=Decimal("0.001"),
            slippage_bps=Decimal("0.0005"),
        )
        order = _market_order(side=OrderSide.SELL)
        fill = engine.try_fill_market(
            order,
            last_price=Decimal("50000"),
            bid=Decimal("49999"),
            ask=Decimal("50001"),
        )
        assert fill is not None
        # Expected price: bid * (1 - slippage) = 49999 * 0.9995
        expected_price = Decimal("49999") * Decimal("0.9995")
        assert fill.price == expected_price.quantize(Decimal("0.00000001"))

    def test_sell_fills_at_last_price_when_no_bid(self):
        engine = MatchingEngine(slippage_bps=Decimal("0.0005"))
        order = _market_order(side=OrderSide.SELL)
        fill = engine.try_fill_market(
            order,
            last_price=Decimal("50000"),
            bid=None,
            ask=None,
        )
        assert fill is not None
        expected_price = Decimal("50000") * Decimal("0.9995")
        assert fill.price == expected_price.quantize(Decimal("0.00000001"))

    def test_returns_none_when_last_price_is_zero(self):
        engine = MatchingEngine()
        order = _market_order()
        fill = engine.try_fill_market(order, last_price=Decimal("0"))
        assert fill is None

    def test_returns_none_when_last_price_is_negative(self):
        engine = MatchingEngine()
        order = _market_order()
        fill = engine.try_fill_market(order, last_price=Decimal("-100"))
        assert fill is None

    def test_market_fill_is_complete(self):
        engine = MatchingEngine()
        order = _market_order(quantity=Decimal("5"))
        fill = engine.try_fill_market(order, last_price=Decimal("100"))
        assert fill is not None
        assert fill.is_complete is True
        assert fill.quantity == Decimal("5")

    def test_returns_none_for_limit_order(self):
        engine = MatchingEngine()
        order = _limit_order()
        fill = engine.try_fill_market(order, last_price=Decimal("50000"))
        assert fill is None


# ---------------------------------------------------------------------------
# Limit order fills
# ---------------------------------------------------------------------------

class TestLimitOrderFills:
    """Test limit order fill simulation."""

    def test_buy_fills_when_ask_at_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.BUY, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49900"),
            ask=Decimal("50000"),
        )
        assert fill is not None
        # Fill price is min(limit, ask) = min(50000, 50000) = 50000
        assert fill.price == Decimal("50000").quantize(Decimal("0.00000001"))

    def test_buy_fills_when_ask_below_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.BUY, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49800"),
            ask=Decimal("49900"),
        )
        assert fill is not None
        # Fill price is min(limit, ask) = min(50000, 49900) = 49900
        assert fill.price == Decimal("49900").quantize(Decimal("0.00000001"))

    def test_buy_does_not_fill_when_ask_above_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.BUY, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("50000"),
            ask=Decimal("50100"),
        )
        assert fill is None

    def test_sell_fills_when_bid_at_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.SELL, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("50000"),
            ask=Decimal("50100"),
        )
        assert fill is not None
        # Fill price is max(limit, bid) = max(50000, 50000) = 50000
        assert fill.price == Decimal("50000").quantize(Decimal("0.00000001"))

    def test_sell_fills_when_bid_above_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.SELL, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("50100"),
            ask=Decimal("50200"),
        )
        assert fill is not None
        # Fill price is max(limit, bid) = max(50000, 50100) = 50100
        assert fill.price == Decimal("50100").quantize(Decimal("0.00000001"))

    def test_sell_does_not_fill_when_bid_below_limit(self):
        engine = MatchingEngine()
        order = _limit_order(side=OrderSide.SELL, price=Decimal("50000"))
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49900"),
            ask=Decimal("50100"),
        )
        assert fill is None

    def test_limit_fill_is_complete(self):
        engine = MatchingEngine()
        order = _limit_order(
            side=OrderSide.BUY,
            price=Decimal("50000"),
            quantity=Decimal("10"),
        )
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49900"),
            ask=Decimal("49950"),
        )
        assert fill is not None
        assert fill.is_complete is True
        assert fill.quantity == Decimal("10")

    def test_returns_none_for_market_order(self):
        engine = MatchingEngine()
        order = _market_order()
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49999"),
            ask=Decimal("50001"),
        )
        assert fill is None

    def test_returns_none_when_no_price_on_order(self):
        engine = MatchingEngine()
        order = PaperOrderState(
            exchange_order_id="exch-003",
            client_order_id="client-003",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
            price=None,
        )
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("49999"),
            ask=Decimal("50001"),
        )
        assert fill is None


# ---------------------------------------------------------------------------
# Commission calculation
# ---------------------------------------------------------------------------

class TestCommissionCalculation:
    """Test that commissions are computed correctly."""

    def test_market_order_commission(self):
        engine = MatchingEngine(
            commission_rate=Decimal("0.001"),
            slippage_bps=Decimal("0"),
        )
        order = _market_order(
            side=OrderSide.BUY,
            quantity=Decimal("2"),
        )
        fill = engine.try_fill_market(order, last_price=Decimal("50000"))
        assert fill is not None
        # Commission = 2 * 50000 * 0.001 = 100
        expected = (Decimal("2") * Decimal("50000") * Decimal("0.001")).quantize(
            Decimal("0.00000001")
        )
        assert fill.commission == expected

    def test_limit_order_commission(self):
        engine = MatchingEngine(commission_rate=Decimal("0.001"))
        order = _limit_order(
            side=OrderSide.BUY,
            price=Decimal("1000"),
            quantity=Decimal("5"),
        )
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("990"),
            ask=Decimal("999"),
        )
        assert fill is not None
        # Fill price = min(1000, 999) = 999
        # Commission = 5 * 999 * 0.001 = 4.995
        expected = (Decimal("5") * Decimal("999") * Decimal("0.001")).quantize(
            Decimal("0.00000001")
        )
        assert fill.commission == expected

    def test_zero_commission_rate(self):
        engine = MatchingEngine(commission_rate=Decimal("0"))
        order = _market_order(quantity=Decimal("10"))
        fill = engine.try_fill_market(order, last_price=Decimal("100"))
        assert fill is not None
        assert fill.commission == Decimal("0")


# ---------------------------------------------------------------------------
# Commission asset resolution
# ---------------------------------------------------------------------------

class TestGetCommissionAsset:
    """Test _get_commission_asset returns the correct quote currency."""

    def test_usdt_pair(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("BTCUSDT", OrderSide.BUY) == "USDT"

    def test_usdc_pair(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("ETHUSDC", OrderSide.SELL) == "USDC"

    def test_busd_pair(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("SOLBUSD", OrderSide.BUY) == "BUSD"

    def test_btc_pair(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("ETHBTC", OrderSide.SELL) == "BTC"

    def test_eth_pair(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("LINKETH", OrderSide.BUY) == "ETH"

    def test_unknown_pair_defaults_to_usdt(self):
        engine = MatchingEngine()
        assert engine._get_commission_asset("XYZABC", OrderSide.BUY) == "USDT"

    def test_market_fill_commission_asset(self):
        engine = MatchingEngine()
        order = _market_order(symbol="ETHUSDC")
        fill = engine.try_fill_market(order, last_price=Decimal("3000"))
        assert fill is not None
        assert fill.commission_asset == "USDC"


# ---------------------------------------------------------------------------
# Partial fill handling
# ---------------------------------------------------------------------------

class TestPartialFills:
    """Test that remaining quantity is correctly computed for partial fills."""

    def test_market_fill_respects_filled_quantity(self):
        engine = MatchingEngine(slippage_bps=Decimal("0"))
        order = _market_order(
            quantity=Decimal("10"),
            filled_quantity=Decimal("3"),
        )
        fill = engine.try_fill_market(order, last_price=Decimal("100"))
        assert fill is not None
        assert fill.quantity == Decimal("7")

    def test_limit_fill_respects_filled_quantity(self):
        engine = MatchingEngine()
        order = _limit_order(
            side=OrderSide.BUY,
            price=Decimal("100"),
            quantity=Decimal("10"),
            filled_quantity=Decimal("6"),
        )
        fill = engine.try_fill_limit(
            order,
            bid=Decimal("99"),
            ask=Decimal("100"),
        )
        assert fill is not None
        assert fill.quantity == Decimal("4")

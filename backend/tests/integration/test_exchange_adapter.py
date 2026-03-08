"""
Integration tests for the PaperExchangeAdapter.

Tests the paper trading adapter's lifecycle, order placement (market and
limit), cancellation, balance tracking, and property accessors.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
import pytest_asyncio

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.paper.adapter import PaperExchangeAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def adapter():
    """Fresh PaperExchangeAdapter with seeded balances and prices."""
    adapter = PaperExchangeAdapter(
        initial_balances={"USDT": Decimal("100000"), "BTC": Decimal("1")},
        commission_rate=Decimal("0.001"),
    )
    await adapter.connect()

    # Seed BTC market price
    adapter.update_market_price(
        "BTCUSDT",
        bid=Decimal("49999"),
        ask=Decimal("50001"),
        last=Decimal("50000"),
    )

    yield adapter
    await adapter.disconnect()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_disconnect_lifecycle():
    """Adapter transitions through connected and disconnected states."""
    adapter = PaperExchangeAdapter(
        initial_balances={"USDT": Decimal("10000")},
    )

    # Before connect
    assert adapter.is_connected is False

    # After connect
    await adapter.connect()
    assert adapter.is_connected is True
    assert await adapter.ping() is True

    # After disconnect
    await adapter.disconnect()
    assert adapter.is_connected is False
    assert await adapter.ping() is False


@pytest.mark.asyncio
async def test_place_market_buy_fills_immediately(adapter):
    """A market BUY order should fill immediately when prices are seeded."""
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.1"),
        client_order_id="market-buy-001",
    )

    assert result.success is True
    assert result.status == "FILLED"
    assert result.exchange_order_id.startswith("PAPER-")
    assert result.client_order_id == "market-buy-001"


@pytest.mark.asyncio
async def test_place_limit_buy_does_not_fill_immediately(adapter):
    """A limit BUY below the ask should not fill immediately."""
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("48000"),  # Well below current ask of 50001
        client_order_id="limit-buy-001",
    )

    assert result.success is True
    assert result.status == "NEW"
    assert result.exchange_order_id.startswith("PAPER-")

    # The order should appear in open orders
    open_orders = await adapter.get_open_orders("BTCUSDT")
    assert len(open_orders) >= 1
    order_ids = [o.exchange_order_id for o in open_orders]
    assert result.exchange_order_id in order_ids


@pytest.mark.asyncio
async def test_limit_order_fills_when_price_crosses(adapter):
    """A limit BUY should fill when ask drops to or below the limit price."""
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("48000"),
        client_order_id="limit-cross-001",
    )

    assert result.status == "NEW"

    # Verify it is open
    open_before = await adapter.get_open_orders("BTCUSDT")
    assert any(o.exchange_order_id == result.exchange_order_id for o in open_before)

    # Update price so that ask drops to the limit price
    adapter.update_market_price(
        "BTCUSDT",
        bid=Decimal("47999"),
        ask=Decimal("48000"),  # ask == limit price -> should fill
        last=Decimal("48000"),
    )

    # Allow the async fill task to run
    await asyncio.sleep(0.05)

    # After fill, the order should no longer be in open orders
    open_after = await adapter.get_open_orders("BTCUSDT")
    filled_ids = [o.exchange_order_id for o in open_after]
    assert result.exchange_order_id not in filled_ids


@pytest.mark.asyncio
async def test_cancel_open_limit_order(adapter):
    """Cancelling an open limit order should succeed."""
    place_result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("45000"),
        client_order_id="cancel-me-001",
    )

    assert place_result.status == "NEW"

    cancel_result = await adapter.cancel_order(
        symbol="BTCUSDT",
        exchange_order_id=place_result.exchange_order_id,
    )

    assert cancel_result.success is True
    assert cancel_result.exchange_order_id == place_result.exchange_order_id

    # Order should no longer be in open orders
    open_orders = await adapter.get_open_orders("BTCUSDT")
    order_ids = [o.exchange_order_id for o in open_orders]
    assert place_result.exchange_order_id not in order_ids


@pytest.mark.asyncio
async def test_cancel_nonexistent_order(adapter):
    """Cancelling an order that does not exist should return success=False."""
    cancel_result = await adapter.cancel_order(
        symbol="BTCUSDT",
        exchange_order_id="PAPER-DOESNOTEXIST",
    )

    assert cancel_result.success is False


@pytest.mark.asyncio
async def test_get_balances_returns_initial(adapter):
    """get_balances should return the initial seeded balances."""
    balances = await adapter.get_balances()

    balance_map = {b.asset: b.total for b in balances}
    assert balance_map["USDT"] == Decimal("100000")
    assert balance_map["BTC"] == Decimal("1")


@pytest.mark.asyncio
async def test_balance_updates_after_market_buy(adapter):
    """After a market BUY fill, USDT should decrease and BTC should increase."""
    balances_before = await adapter.get_balances()
    before_map = {b.asset: b.total for b in balances_before}
    usdt_before = before_map["USDT"]
    btc_before = before_map["BTC"]

    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.1"),
        client_order_id="balance-test-001",
    )

    assert result.status == "FILLED"

    balances_after = await adapter.get_balances()
    after_map = {b.asset: b.total for b in balances_after}

    # BTC balance should increase by the fill quantity
    assert after_map["BTC"] == btc_before + Decimal("0.1")

    # USDT balance should decrease (notional + commission)
    assert after_map["USDT"] < usdt_before


@pytest.mark.asyncio
async def test_balance_updates_after_market_sell(adapter):
    """After a market SELL fill, BTC should decrease and USDT should increase."""
    balances_before = await adapter.get_balances()
    before_map = {b.asset: b.total for b in balances_before}
    usdt_before = before_map["USDT"]
    btc_before = before_map["BTC"]

    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.5"),
        client_order_id="sell-test-001",
    )

    assert result.status == "FILLED"

    balances_after = await adapter.get_balances()
    after_map = {b.asset: b.total for b in balances_after}

    # BTC balance should decrease by the fill quantity
    assert after_map["BTC"] == btc_before - Decimal("0.5")

    # USDT balance should increase (notional - commission)
    assert after_map["USDT"] > usdt_before


@pytest.mark.asyncio
async def test_exchange_name_and_is_paper(adapter):
    """exchange_name should be 'paper' and is_paper should be True."""
    assert adapter.exchange_name == "paper"
    assert adapter.is_paper is True


@pytest.mark.asyncio
async def test_market_order_rejected_without_price():
    """A market order should be rejected when no market price is available."""
    adapter = PaperExchangeAdapter(
        initial_balances={"USDT": Decimal("100000")},
    )
    await adapter.connect()

    # Do NOT seed any prices
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        client_order_id="no-price-001",
    )

    assert result.success is False
    assert result.status == "REJECTED"

    await adapter.disconnect()


@pytest.mark.asyncio
async def test_place_order_generates_exchange_order_id(adapter):
    """Every placed order should have a unique PAPER-prefixed exchange ID."""
    results = []
    for i in range(3):
        r = await adapter.place_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            price=Decimal("40000"),
            client_order_id=f"unique-test-{i}",
        )
        results.append(r)

    exchange_ids = [r.exchange_order_id for r in results]
    assert all(eid.startswith("PAPER-") for eid in exchange_ids)

    # All IDs should be unique
    assert len(set(exchange_ids)) == len(exchange_ids)


@pytest.mark.asyncio
async def test_get_open_orders_filters_by_symbol(adapter):
    """get_open_orders(symbol) should only return orders for that symbol."""
    # Seed ETH price
    adapter.update_market_price(
        "ETHUSDT",
        bid=Decimal("2999"),
        ask=Decimal("3001"),
        last=Decimal("3000"),
    )

    # Place limit orders on two different symbols
    await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("40000"),
        client_order_id="btc-limit",
    )
    await adapter.place_order(
        symbol="ETHUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("2500"),
        client_order_id="eth-limit",
    )

    btc_orders = await adapter.get_open_orders("BTCUSDT")
    eth_orders = await adapter.get_open_orders("ETHUSDT")

    assert all(o.symbol == "BTCUSDT" for o in btc_orders)
    assert all(o.symbol == "ETHUSDT" for o in eth_orders)
    assert len(btc_orders) >= 1
    assert len(eth_orders) >= 1


@pytest.mark.asyncio
async def test_cancel_order_by_client_id(adapter):
    """Cancelling an order by client_order_id should work."""
    place_result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("42000"),
        client_order_id="cancel-by-client-id",
    )

    assert place_result.status == "NEW"

    cancel_result = await adapter.cancel_order(
        symbol="BTCUSDT",
        client_order_id="cancel-by-client-id",
    )

    assert cancel_result.success is True

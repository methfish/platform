"""
End-to-end tests for the order lifecycle.

Tests a full order flow: paper adapter order placement -> fill ->
position tracker application -> PnL computation. Uses mock Position
objects to avoid requiring a real database session.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from app.core.enums import OrderSide, OrderType, PositionSide
from app.exchange.paper.adapter import PaperExchangeAdapter
from app.position.pnl import compute_unrealized_pnl
from app.position.tracker import PositionTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_position(**overrides):
    """Create a mock Position in FLAT state with zeroed fields."""
    pos = MagicMock()
    pos.quantity = overrides.get("quantity", Decimal("0"))
    pos.avg_entry_price = overrides.get("avg_entry_price", Decimal("0"))
    pos.realized_pnl = overrides.get("realized_pnl", Decimal("0"))
    pos.unrealized_pnl = overrides.get("unrealized_pnl", Decimal("0"))
    pos.total_commission = overrides.get("total_commission", Decimal("0"))
    pos.side = overrides.get("side", PositionSide.FLAT.value)
    pos.opened_at = overrides.get("opened_at", None)
    return pos


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def adapter():
    """Paper adapter with balances and BTC price seeded."""
    adapter = PaperExchangeAdapter(
        initial_balances={"USDT": Decimal("100000"), "BTC": Decimal("1")},
        commission_rate=Decimal("0.001"),
    )
    await adapter.connect()
    adapter.update_market_price(
        "BTCUSDT",
        bid=Decimal("49999"),
        ask=Decimal("50001"),
        last=Decimal("50000"),
    )
    yield adapter
    await adapter.disconnect()


@pytest.fixture
def tracker():
    """PositionTracker instance."""
    return PositionTracker()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_buy_lifecycle(adapter, tracker):
    """
    Place a market BUY on the paper adapter, get the fill, apply it
    to a position via the tracker, and verify the position is LONG
    with the correct entry price.
    """
    # Step 1: Place market BUY
    result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.5"),
        client_order_id="lifecycle-buy-001",
    )
    assert result.success is True
    assert result.status == "FILLED"

    # Step 2: Simulate receiving the fill and applying to position
    # The fill price is ask * (1 + slippage_bps) for a BUY.
    # With ask=50001 and default slippage=0.0005:
    #   fill_price = 50001 * 1.0005 = ~50026.0005
    # We'll use an approximate value for the position update.
    fill_price = Decimal("50001") * (Decimal("1") + Decimal("0.0005"))
    fill_price = fill_price.quantize(Decimal("0.00000001"))
    commission = Decimal("0.5") * fill_price * Decimal("0.001")
    commission = commission.quantize(Decimal("0.00000001"))

    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("0.5"), fill_price, commission)

    # Step 3: Verify position state
    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("0.5")
    assert pos.avg_entry_price == fill_price
    assert pos.total_commission == commission
    assert pos.realized_pnl == Decimal("0")
    assert pos.opened_at is not None


@pytest.mark.asyncio
async def test_full_sell_to_close_lifecycle(adapter, tracker):
    """
    Open a LONG position via BUY, then close it with a SELL at a
    higher price. Verify position goes FLAT and realized PnL is correct.
    """
    # Step 1: Open LONG at 50000
    entry_price = Decimal("50000")
    buy_commission = Decimal("0.5") * entry_price * Decimal("0.001")

    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("0.5"), entry_price, buy_commission)

    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("0.5")

    # Step 2: Close LONG at 52000 (price moved up -> profit)
    exit_price = Decimal("52000")
    sell_commission = Decimal("0.5") * exit_price * Decimal("0.001")

    pos = tracker._apply_sell(pos, Decimal("0.5"), exit_price, sell_commission)

    # Step 3: Verify position goes FLAT
    assert pos.side == PositionSide.FLAT.value
    assert pos.quantity == Decimal("0")

    # Step 4: Verify realized PnL
    # PnL = close_qty * (exit_price - entry_price) = 0.5 * (52000 - 50000) = 1000
    expected_pnl = Decimal("0.5") * (exit_price - entry_price)
    assert pos.realized_pnl == expected_pnl

    # Commission should be the sum of both fills
    assert pos.total_commission == buy_commission + sell_commission


@pytest.mark.asyncio
async def test_partial_close(tracker):
    """
    Buy 1 BTC, sell 0.5 BTC. Position should remain LONG with 0.5 qty.
    """
    entry_price = Decimal("50000")
    buy_commission = Decimal("1") * entry_price * Decimal("0.001")

    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("1"), entry_price, buy_commission)

    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("1")

    # Partial close: sell 0.5 at 51000
    exit_price = Decimal("51000")
    sell_commission = Decimal("0.5") * exit_price * Decimal("0.001")

    pos = tracker._apply_sell(pos, Decimal("0.5"), exit_price, sell_commission)

    # Position should still be LONG with 0.5 remaining
    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("0.5")

    # Realized PnL from the partial close: 0.5 * (51000 - 50000) = 500
    expected_partial_pnl = Decimal("0.5") * (exit_price - entry_price)
    assert pos.realized_pnl == expected_partial_pnl

    # Average entry price should remain unchanged
    assert pos.avg_entry_price == entry_price


@pytest.mark.asyncio
async def test_position_flip_long_to_short(tracker):
    """
    LONG 0.5 BTC, then SELL 1.0 BTC -> position should flip to SHORT 0.5 BTC.
    """
    entry_price = Decimal("50000")
    buy_commission = Decimal("0.5") * entry_price * Decimal("0.001")

    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("0.5"), entry_price, buy_commission)

    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("0.5")

    # Sell 1.0 BTC at 48000 -> close 0.5 long, open 0.5 short
    sell_price = Decimal("48000")
    sell_commission = Decimal("1") * sell_price * Decimal("0.001")

    pos = tracker._apply_sell(pos, Decimal("1"), sell_price, sell_commission)

    # Position should have flipped to SHORT with 0.5 qty
    assert pos.side == PositionSide.SHORT.value
    assert pos.quantity == Decimal("0.5")

    # Realized PnL from closing the long: 0.5 * (48000 - 50000) = -1000
    expected_pnl = Decimal("0.5") * (sell_price - entry_price)
    assert pos.realized_pnl == expected_pnl

    # The new short position should have avg_entry_price = sell_price
    assert pos.avg_entry_price == sell_price


@pytest.mark.asyncio
async def test_unrealized_pnl_long_position():
    """
    Open a LONG position and verify that compute_unrealized_pnl returns
    a positive value when the mark price is above entry.
    """
    entry_price = Decimal("50000")
    quantity = Decimal("1")
    mark_price = Decimal("55000")

    unrealized = compute_unrealized_pnl(
        side=PositionSide.LONG.value,
        quantity=quantity,
        avg_entry_price=entry_price,
        mark_price=mark_price,
    )

    # 1 * (55000 - 50000) = 5000
    assert unrealized == Decimal("5000")
    assert unrealized > Decimal("0")


@pytest.mark.asyncio
async def test_unrealized_pnl_short_position():
    """
    Open a SHORT position and verify compute_unrealized_pnl when
    mark price drops (profit for short).
    """
    entry_price = Decimal("50000")
    quantity = Decimal("1")
    mark_price = Decimal("48000")

    unrealized = compute_unrealized_pnl(
        side=PositionSide.SHORT.value,
        quantity=quantity,
        avg_entry_price=entry_price,
        mark_price=mark_price,
    )

    # 1 * (50000 - 48000) = 2000
    assert unrealized == Decimal("2000")
    assert unrealized > Decimal("0")


@pytest.mark.asyncio
async def test_unrealized_pnl_flat_position():
    """A FLAT position should always have zero unrealized PnL."""
    unrealized = compute_unrealized_pnl(
        side=PositionSide.FLAT.value,
        quantity=Decimal("0"),
        avg_entry_price=Decimal("50000"),
        mark_price=Decimal("60000"),
    )

    assert unrealized == Decimal("0")


@pytest.mark.asyncio
async def test_unrealized_pnl_long_at_loss():
    """
    LONG position where mark price is below entry should have negative
    unrealized PnL.
    """
    unrealized = compute_unrealized_pnl(
        side=PositionSide.LONG.value,
        quantity=Decimal("2"),
        avg_entry_price=Decimal("50000"),
        mark_price=Decimal("49000"),
    )

    # 2 * (49000 - 50000) = -2000
    assert unrealized == Decimal("-2000")
    assert unrealized < Decimal("0")


@pytest.mark.asyncio
async def test_end_to_end_buy_sell_with_adapter_and_tracker(adapter, tracker):
    """
    Full end-to-end: place BUY on adapter, apply fill to position,
    then place SELL on adapter, apply fill, verify final state.
    """
    # -- BUY --
    buy_result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.2"),
        client_order_id="e2e-buy",
    )
    assert buy_result.status == "FILLED"

    # Approximate fill price for BUY: ask * (1 + 0.0005)
    buy_fill_price = Decimal("50001") * Decimal("1.0005")
    buy_fill_price = buy_fill_price.quantize(Decimal("0.00000001"))
    buy_commission = Decimal("0.2") * buy_fill_price * Decimal("0.001")
    buy_commission = buy_commission.quantize(Decimal("0.00000001"))

    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("0.2"), buy_fill_price, buy_commission)

    assert pos.side == PositionSide.LONG.value
    assert pos.quantity == Decimal("0.2")

    # -- SELL to close --
    sell_result = await adapter.place_order(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.2"),
        client_order_id="e2e-sell",
    )
    assert sell_result.status == "FILLED"

    # Approximate fill price for SELL: bid * (1 - 0.0005)
    sell_fill_price = Decimal("49999") * Decimal("0.9995")
    sell_fill_price = sell_fill_price.quantize(Decimal("0.00000001"))
    sell_commission = Decimal("0.2") * sell_fill_price * Decimal("0.001")
    sell_commission = sell_commission.quantize(Decimal("0.00000001"))

    pos = tracker._apply_sell(pos, Decimal("0.2"), sell_fill_price, sell_commission)

    assert pos.side == PositionSide.FLAT.value
    assert pos.quantity == Decimal("0")

    # There should be a small negative realized PnL due to spread + slippage
    # buy_fill_price > sell_fill_price, so PnL = 0.2 * (sell - buy) < 0
    assert pos.realized_pnl < Decimal("0")

    # Total commission is sum of both legs
    assert pos.total_commission == buy_commission + sell_commission


@pytest.mark.asyncio
async def test_tracker_update_unrealized_pnl(tracker):
    """
    PositionTracker.update_unrealized_pnl should correctly update the
    position's unrealized_pnl field.
    """
    pos = _make_flat_position()
    pos = tracker._apply_buy(pos, Decimal("1"), Decimal("50000"), Decimal("50"))

    assert pos.side == PositionSide.LONG.value

    # Mark price moved up to 52000
    pnl = tracker.update_unrealized_pnl(pos, mark_price=Decimal("52000"))

    # 1 * (52000 - 50000) = 2000
    assert pnl == Decimal("2000")
    assert pos.unrealized_pnl == Decimal("2000")

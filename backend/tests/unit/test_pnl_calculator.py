"""
Unit tests for the PnL calculator.

Tests compute_unrealized_pnl for all position sides and
PnLSummary aggregation / serialization.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from app.core.enums import PositionSide
from app.position.pnl import PnLSummary, compute_pnl_summary, compute_unrealized_pnl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_position(
    realized_pnl: Decimal = Decimal("0"),
    unrealized_pnl: Decimal = Decimal("0"),
    total_commission: Decimal = Decimal("0"),
    side: str = "LONG",
    quantity: Decimal = Decimal("1"),
) -> MagicMock:
    """Create a mock Position with the needed attributes."""
    pos = MagicMock()
    pos.realized_pnl = realized_pnl
    pos.unrealized_pnl = unrealized_pnl
    pos.total_commission = total_commission
    pos.side = side
    pos.quantity = quantity
    return pos


# ---------------------------------------------------------------------------
# compute_unrealized_pnl
# ---------------------------------------------------------------------------

class TestComputeUnrealizedPnl:
    """Test per-position unrealized PnL calculation."""

    def test_long_position_with_profit(self):
        # Bought at 100, now at 120, qty 10 -> profit = 10 * (120 - 100) = 200
        result = compute_unrealized_pnl(
            side=PositionSide.LONG.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("120"),
        )
        assert result == Decimal("200")

    def test_long_position_with_loss(self):
        # Bought at 100, now at 80, qty 10 -> loss = 10 * (80 - 100) = -200
        result = compute_unrealized_pnl(
            side=PositionSide.LONG.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("80"),
        )
        assert result == Decimal("-200")

    def test_short_position_with_profit(self):
        # Sold at 100, now at 80, qty 10 -> profit = 10 * (100 - 80) = 200
        result = compute_unrealized_pnl(
            side=PositionSide.SHORT.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("80"),
        )
        assert result == Decimal("200")

    def test_short_position_with_loss(self):
        # Sold at 100, now at 120, qty 10 -> loss = 10 * (100 - 120) = -200
        result = compute_unrealized_pnl(
            side=PositionSide.SHORT.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("120"),
        )
        assert result == Decimal("-200")

    def test_flat_position_returns_zero(self):
        result = compute_unrealized_pnl(
            side=PositionSide.FLAT.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("120"),
        )
        assert result == Decimal("0")

    def test_zero_quantity_returns_zero(self):
        result = compute_unrealized_pnl(
            side=PositionSide.LONG.value,
            quantity=Decimal("0"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("120"),
        )
        assert result == Decimal("0")

    def test_negative_quantity_returns_zero(self):
        result = compute_unrealized_pnl(
            side=PositionSide.LONG.value,
            quantity=Decimal("-5"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("120"),
        )
        assert result == Decimal("0")

    def test_long_breakeven_returns_zero(self):
        result = compute_unrealized_pnl(
            side=PositionSide.LONG.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("100"),
        )
        assert result == Decimal("0")

    def test_short_breakeven_returns_zero(self):
        result = compute_unrealized_pnl(
            side=PositionSide.SHORT.value,
            quantity=Decimal("10"),
            avg_entry_price=Decimal("100"),
            mark_price=Decimal("100"),
        )
        assert result == Decimal("0")


# ---------------------------------------------------------------------------
# PnLSummary
# ---------------------------------------------------------------------------

class TestPnLSummary:
    """Test the PnLSummary dataclass properties and serialization."""

    def test_gross_pnl_calculation(self):
        summary = PnLSummary(
            total_realized_pnl=Decimal("500"),
            total_unrealized_pnl=Decimal("300"),
            total_commission=Decimal("50"),
            net_pnl=Decimal("750"),
            position_count=2,
        )
        assert summary.gross_pnl == Decimal("800")

    def test_gross_pnl_with_negative_values(self):
        summary = PnLSummary(
            total_realized_pnl=Decimal("-200"),
            total_unrealized_pnl=Decimal("100"),
        )
        assert summary.gross_pnl == Decimal("-100")

    def test_to_dict_format(self):
        summary = PnLSummary(
            total_realized_pnl=Decimal("500"),
            total_unrealized_pnl=Decimal("300"),
            total_commission=Decimal("50"),
            net_pnl=Decimal("750"),
            position_count=2,
        )
        d = summary.to_dict()

        assert d["total_realized_pnl"] == "500"
        assert d["total_unrealized_pnl"] == "300"
        assert d["total_commission"] == "50"
        assert d["net_pnl"] == "750"
        assert d["gross_pnl"] == "800"
        assert d["position_count"] == 2

    def test_to_dict_keys(self):
        summary = PnLSummary()
        d = summary.to_dict()
        expected_keys = {
            "total_realized_pnl",
            "total_unrealized_pnl",
            "total_commission",
            "net_pnl",
            "gross_pnl",
            "position_count",
        }
        assert set(d.keys()) == expected_keys

    def test_default_values(self):
        summary = PnLSummary()
        assert summary.total_realized_pnl == Decimal("0")
        assert summary.total_unrealized_pnl == Decimal("0")
        assert summary.total_commission == Decimal("0")
        assert summary.net_pnl == Decimal("0")
        assert summary.position_count == 0
        assert summary.gross_pnl == Decimal("0")


# ---------------------------------------------------------------------------
# compute_pnl_summary
# ---------------------------------------------------------------------------

class TestComputePnlSummary:
    """Test aggregate PnL computation from a list of positions."""

    def test_single_active_position(self):
        positions = [
            _mock_position(
                realized_pnl=Decimal("100"),
                unrealized_pnl=Decimal("50"),
                total_commission=Decimal("10"),
                side="LONG",
                quantity=Decimal("5"),
            ),
        ]
        summary = compute_pnl_summary(positions)
        assert summary.total_realized_pnl == Decimal("100")
        assert summary.total_unrealized_pnl == Decimal("50")
        assert summary.total_commission == Decimal("10")
        assert summary.net_pnl == Decimal("140")  # 100 + 50 - 10
        assert summary.position_count == 1

    def test_multiple_positions(self):
        positions = [
            _mock_position(
                realized_pnl=Decimal("100"),
                unrealized_pnl=Decimal("50"),
                total_commission=Decimal("10"),
                side="LONG",
                quantity=Decimal("5"),
            ),
            _mock_position(
                realized_pnl=Decimal("-30"),
                unrealized_pnl=Decimal("20"),
                total_commission=Decimal("5"),
                side="SHORT",
                quantity=Decimal("3"),
            ),
        ]
        summary = compute_pnl_summary(positions)
        assert summary.total_realized_pnl == Decimal("70")
        assert summary.total_unrealized_pnl == Decimal("70")
        assert summary.total_commission == Decimal("15")
        assert summary.net_pnl == Decimal("125")  # 70 + 70 - 15
        assert summary.position_count == 2

    def test_flat_positions_not_counted(self):
        positions = [
            _mock_position(
                realized_pnl=Decimal("100"),
                unrealized_pnl=Decimal("0"),
                total_commission=Decimal("10"),
                side=PositionSide.FLAT.value,
                quantity=Decimal("0"),
            ),
        ]
        summary = compute_pnl_summary(positions)
        assert summary.position_count == 0
        # PnL is still aggregated even for flat positions
        assert summary.total_realized_pnl == Decimal("100")

    def test_empty_positions_list(self):
        summary = compute_pnl_summary([])
        assert summary.total_realized_pnl == Decimal("0")
        assert summary.total_unrealized_pnl == Decimal("0")
        assert summary.total_commission == Decimal("0")
        assert summary.net_pnl == Decimal("0")
        assert summary.position_count == 0

    def test_zero_quantity_position_not_counted(self):
        positions = [
            _mock_position(
                realized_pnl=Decimal("200"),
                unrealized_pnl=Decimal("0"),
                total_commission=Decimal("5"),
                side="LONG",
                quantity=Decimal("0"),
            ),
        ]
        summary = compute_pnl_summary(positions)
        assert summary.position_count == 0

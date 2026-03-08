"""
Unit tests for the market data normalizer.

Tests normalize_ticker_from_raw with various input types
(float, string, Decimal) and verifies output structure.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.market_data.normalizer import normalize_ticker_from_raw
from app.exchange.models import NormalizedTicker


# ---------------------------------------------------------------------------
# normalize_ticker_from_raw
# ---------------------------------------------------------------------------

class TestNormalizeTickerFromRaw:
    """Test creation of NormalizedTicker from raw exchange values."""

    def test_basic_ticker_creation(self):
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="binance_spot",
            bid=Decimal("49999"),
            ask=Decimal("50001"),
            last=Decimal("50000"),
            volume=Decimal("1000"),
        )
        assert isinstance(ticker, NormalizedTicker)
        assert ticker.symbol == "BTCUSDT"
        assert ticker.exchange == "binance_spot"
        assert ticker.bid == Decimal("49999")
        assert ticker.ask == Decimal("50001")
        assert ticker.last == Decimal("50000")
        assert ticker.volume_24h == Decimal("1000")

    def test_symbol_is_uppercased(self):
        ticker = normalize_ticker_from_raw(
            symbol="btcusdt",
            exchange="binance_spot",
            bid="49999",
            ask="50001",
            last="50000",
        )
        assert ticker.symbol == "BTCUSDT"

    def test_accepts_float_inputs(self):
        ticker = normalize_ticker_from_raw(
            symbol="ETHUSDT",
            exchange="binance_spot",
            bid=2999.5,
            ask=3000.5,
            last=3000.0,
            volume=5000.0,
        )
        assert ticker.bid == Decimal("2999.5")
        assert ticker.ask == Decimal("3000.5")
        assert ticker.last == Decimal("3000.0")
        assert ticker.volume_24h == Decimal("5000.0")

    def test_accepts_string_inputs(self):
        ticker = normalize_ticker_from_raw(
            symbol="SOLUSDT",
            exchange="binance_spot",
            bid="99.9",
            ask="100.1",
            last="100.0",
            volume="50000",
        )
        assert ticker.bid == Decimal("99.9")
        assert ticker.ask == Decimal("100.1")
        assert ticker.last == Decimal("100.0")
        assert ticker.volume_24h == Decimal("50000")

    def test_accepts_decimal_inputs(self):
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="paper",
            bid=Decimal("49999.12345678"),
            ask=Decimal("50001.87654321"),
            last=Decimal("50000.50000000"),
        )
        assert ticker.bid == Decimal("49999.12345678")
        assert ticker.ask == Decimal("50001.87654321")
        assert ticker.last == Decimal("50000.50000000")

    def test_default_volume_is_zero(self):
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="binance_spot",
            bid="49999",
            ask="50001",
            last="50000",
        )
        assert ticker.volume_24h == Decimal("0")

    def test_timestamp_is_set(self):
        before = datetime.now(timezone.utc)
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="binance_spot",
            bid="49999",
            ask="50001",
            last="50000",
        )
        after = datetime.now(timezone.utc)
        assert ticker.timestamp is not None
        assert before <= ticker.timestamp <= after

    def test_exchange_preserved_as_is(self):
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="binance_futures",
            bid="49999",
            ask="50001",
            last="50000",
        )
        assert ticker.exchange == "binance_futures"

    def test_mixed_input_types(self):
        """Verify that mixing float, string, and Decimal inputs all work."""
        ticker = normalize_ticker_from_raw(
            symbol="ETHUSDT",
            exchange="paper",
            bid=2999.5,           # float
            ask="3000.5",         # string
            last=Decimal("3000"), # Decimal
            volume=10000,         # int (coerced via float path)
        )
        assert ticker.bid == Decimal("2999.5")
        assert ticker.ask == Decimal("3000.5")
        assert ticker.last == Decimal("3000")
        assert ticker.volume_24h == Decimal("10000")

    def test_zero_values(self):
        ticker = normalize_ticker_from_raw(
            symbol="BTCUSDT",
            exchange="paper",
            bid=0,
            ask=0,
            last=0,
            volume=0,
        )
        assert ticker.bid == Decimal("0")
        assert ticker.ask == Decimal("0")
        assert ticker.last == Decimal("0")
        assert ticker.volume_24h == Decimal("0")

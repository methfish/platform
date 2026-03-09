"""
Tests for P0/P1 remediation fixes.

Covers:
  - Fix A: Sandbox security (__import__ blocked)
  - Fix B: register_strategy() signature alignment
  - Fix C: Migration file structure (sanity check)
  - Fix D: Equity curve field consistency (verified no-op)
  - Fix E: Paper adapter balance validation
  - Fix F: Bar query LIMIT constant exists
"""

import ast
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.enums import OrderSide, OrderType, TimeInForce
from app.exchange.paper.adapter import PaperExchangeAdapter
from app.exchange.paper.book import PaperOrderBook
from app.backtest.strategy_loader import (
    SAFE_BUILTINS,
    validate_source,
    compile_strategy,
    register_strategy_runtime,
)


# ====================================================================
# Fix A: Sandbox security — __import__ must NOT be in safe builtins
# ====================================================================


class TestSandboxSecurity:
    """Verify that __import__ is not exposed in any sandbox dict."""

    def test_safe_builtins_no_import(self):
        """SAFE_BUILTINS in strategy_loader must not contain __import__."""
        assert "__import__" not in SAFE_BUILTINS
        assert "import" not in SAFE_BUILTINS

    def test_safe_builtins_has_decimal(self):
        """Decimal must be directly provided so strategies can use it."""
        assert "Decimal" in SAFE_BUILTINS
        assert SAFE_BUILTINS["Decimal"] is Decimal

    def test_backtest_verification_sandbox_no_import(self):
        """backtest_verification _compile_and_extract sandbox must block __import__."""
        from app.agents.coding_agent.skills.backtest_verification import (
            _compile_and_extract,
        )

        malicious_code = '''
def signal_fn(bar, params, state):
    os = __import__("os")
    return "HOLD", bar.close, "pwned"
'''
        with pytest.raises(Exception):
            fn = _compile_and_extract(malicious_code)
            # If it compiles, calling it must fail because __import__ is undefined
            from app.agents.coding_agent.skills.backtest_verification import _SimpleBar
            bar = _SimpleBar({
                "timestamp": None, "open": Decimal("1"), "high": Decimal("1"),
                "low": Decimal("1"), "close": Decimal("1"), "volume": Decimal("1"),
                "symbol": "EURUSD", "interval": "1h",
            })
            fn(bar, {}, {})

    def test_code_registration_sandbox_no_import(self):
        """code_registration _compile_signal_fn sandbox must block __import__."""
        from app.agents.coding_agent.skills.code_registration import (
            _compile_signal_fn,
        )

        malicious_code = '''
def signal_fn(bar, params, state):
    os = __import__("os")
    return "HOLD", bar.close, "pwned"
'''
        with pytest.raises(Exception):
            fn = _compile_signal_fn(malicious_code)
            # Must fail at compile or call time
            fn(None, {}, {})

    def test_strategy_loader_blocks_import_statement(self):
        """validate_source must reject code with import statements."""
        code_with_import = '''
import os
def signal_fn(bar, params, state):
    return "HOLD", bar.close, "ok"
'''
        valid, issues = validate_source(code_with_import)
        assert not valid
        assert any("import" in i.lower() for i in issues)

    def test_strategy_loader_blocks_dunder_access(self):
        """validate_source must reject code with __builtins__ access."""
        code_with_dunder = '''
def signal_fn(bar, params, state):
    x = __builtins__
    return "HOLD", bar.close, "ok"
'''
        valid, issues = validate_source(code_with_dunder)
        assert not valid
        assert any("dunder" in i.lower() or "__" in i for i in issues)

    def test_valid_strategy_compiles(self):
        """A safe strategy should compile and run correctly."""
        safe_code = '''
def signal_fn(bar, params, state):
    if bar.close > Decimal("1.1"):
        return "BUY", bar.close, "above threshold"
    return "HOLD", bar.close, "below threshold"
'''
        fn = compile_strategy("test_safe", safe_code)
        assert fn is not None


# ====================================================================
# Fix B: register_strategy() signature
# ====================================================================


class TestRegisterStrategySignature:
    """Verify register_strategy and register_strategy_runtime work correctly."""

    def test_register_strategy_runtime_success(self):
        """register_strategy_runtime should compile and register valid code."""
        code = '''
def signal_fn(bar, params, state):
    return "HOLD", bar.close, "test"
'''
        result = register_strategy_runtime("test_rt_strategy", code)
        assert result is True

        from app.backtest.engine import SIGNAL_GENERATORS
        assert "test_rt_strategy" in SIGNAL_GENERATORS

        # Cleanup
        del SIGNAL_GENERATORS["test_rt_strategy"]

    def test_register_strategy_runtime_rejects_invalid(self):
        """register_strategy_runtime should return False for invalid code."""
        result = register_strategy_runtime("bad_strategy", "import os\nos.system('ls')")
        assert result is False

    @pytest.mark.asyncio
    async def test_register_strategy_async_signature(self):
        """register_strategy (async) must accept the full kwargs from code_registration."""
        from app.backtest.strategy_loader import register_strategy

        # Verify it's a coroutine function with the right params
        import inspect
        sig = inspect.signature(register_strategy)
        param_names = list(sig.parameters.keys())
        assert "session_factory" in param_names
        assert "name" in param_names
        assert "source_code" in param_names
        assert "description" in param_names
        assert "default_params" in param_names
        assert "params_schema" in param_names
        assert "category" in param_names
        assert inspect.iscoroutinefunction(register_strategy)

    def test_register_strategy_return_type_annotation(self):
        """register_strategy return type must be Optional[UUID], not Optional[int]."""
        from app.backtest.strategy_loader import register_strategy
        import inspect
        from uuid import UUID

        sig = inspect.signature(register_strategy)
        # Return annotation should reference UUID, not int
        ret = sig.return_annotation
        # Check that the string representation mentions UUID
        assert "UUID" in str(ret) or ret is UUID or (
            hasattr(ret, "__args__") and UUID in ret.__args__
        )


# ====================================================================
# Fix C: Migration sanity check
# ====================================================================


class TestMigrationFile:
    """Verify migration 004 exists and has correct structure."""

    def test_migration_file_parseable(self):
        """Migration 004 must be valid Python."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migration_004",
            "/Users/matteocrucito/Desktop/platform/backend/alembic/versions/"
            "004_add_backtest_and_generated_strategies.py",
        )
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        # Don't execute — just verify it parses
        with open(spec.origin) as f:
            source = f.read()
        tree = ast.parse(source)
        assert tree is not None

    def test_migration_revision_chain(self):
        """Migration 004 must merge heads 002 and 003."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "migration_004",
            "/Users/matteocrucito/Desktop/platform/backend/alembic/versions/"
            "004_add_backtest_and_generated_strategies.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.revision == "004"
        assert set(module.down_revision) == {"002", "003"}

    def test_migration_creates_generated_strategies_table(self):
        """Migration 004 upgrade must create generated_strategies table."""
        with open(
            "/Users/matteocrucito/Desktop/platform/backend/alembic/versions/"
            "004_add_backtest_and_generated_strategies.py"
        ) as f:
            source = f.read()
        assert '"generated_strategies"' in source
        assert '"backtest_runs"' in source


# ====================================================================
# Fix E: Paper adapter balance validation
# ====================================================================


class TestPaperAdapterBalanceValidation:
    """Verify paper adapter rejects orders when balance is insufficient."""

    def _make_adapter(self, balances: dict[str, Decimal] | None = None) -> PaperExchangeAdapter:
        adapter = PaperExchangeAdapter(
            initial_balances=balances or {"USD": Decimal("10000")},
        )
        adapter._connected = True
        return adapter

    @pytest.mark.asyncio
    async def test_buy_rejected_insufficient_balance(self):
        """BUY order should be rejected if USD balance is too low."""
        adapter = self._make_adapter({"USD": Decimal("100")})
        # Set a price so the market order can check balance
        adapter._book.update_price("EURUSD", Decimal("1.1"), Decimal("1.1"), Decimal("1.1"))

        result = await adapter.place_order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10000"),  # Notional = 11000, balance = 100
        )
        assert result.success is False
        assert result.status == "REJECTED"
        assert "Insufficient" in result.message

    @pytest.mark.asyncio
    async def test_sell_rejected_insufficient_balance(self):
        """SELL order should be rejected if base asset balance is insufficient."""
        adapter = self._make_adapter({"USD": Decimal("10000"), "EUR": Decimal("0")})
        adapter._book.update_price("EURUSD", Decimal("1.1"), Decimal("1.1"), Decimal("1.1"))

        result = await adapter.place_order(
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("10000"),  # Need 10000 EUR, have 0
        )
        assert result.success is False
        assert result.status == "REJECTED"
        assert "Insufficient" in result.message

    @pytest.mark.asyncio
    async def test_buy_accepted_sufficient_balance(self):
        """BUY order should succeed when balance is sufficient."""
        adapter = self._make_adapter({"USD": Decimal("50000")})
        adapter._book.update_price("EURUSD", Decimal("1.1"), Decimal("1.1"), Decimal("1.1"))

        result = await adapter.place_order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10000"),  # Notional = 11000, balance = 50000
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_stock_buy_balance_check(self):
        """Stock BUY should check USD balance (stocks have implicit USD quote)."""
        adapter = self._make_adapter({"USD": Decimal("100")})
        adapter._book.update_price("AAPL", Decimal("150"), Decimal("150"), Decimal("150"))

        result = await adapter.place_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10"),  # Notional = 1500, balance = 100
        )
        assert result.success is False
        assert result.status == "REJECTED"


# ====================================================================
# Fix E (bonus): Symbol parsing
# ====================================================================


class TestSymbolParsing:
    """Verify _parse_symbol handles forex, stocks, and edge cases."""

    def test_eurusd(self):
        base, quote = PaperExchangeAdapter._parse_symbol("EURUSD")
        assert base == "EUR"
        assert quote == "USD"

    def test_usdjpy(self):
        base, quote = PaperExchangeAdapter._parse_symbol("USDJPY")
        assert base == "USD"
        assert quote == "JPY"

    def test_usdchf(self):
        """USDCHF should parse as USD/CHF, not USDCH/F."""
        base, quote = PaperExchangeAdapter._parse_symbol("USDCHF")
        assert base == "USD"
        assert quote == "CHF"

    def test_gbpusd(self):
        base, quote = PaperExchangeAdapter._parse_symbol("GBPUSD")
        assert base == "GBP"
        assert quote == "USD"

    def test_stock_aapl(self):
        """Stocks should default to quote=USD."""
        base, quote = PaperExchangeAdapter._parse_symbol("AAPL")
        assert base == "AAPL"
        assert quote == "USD"

    def test_stock_spy(self):
        base, quote = PaperExchangeAdapter._parse_symbol("SPY")
        assert base == "SPY"
        assert quote == "USD"

    def test_audusd(self):
        base, quote = PaperExchangeAdapter._parse_symbol("AUDUSD")
        assert base == "AUD"
        assert quote == "USD"

    def test_nzdusd(self):
        base, quote = PaperExchangeAdapter._parse_symbol("NZDUSD")
        assert base == "NZD"
        assert quote == "USD"

    def test_usdcad(self):
        base, quote = PaperExchangeAdapter._parse_symbol("USDCAD")
        assert base == "USD"
        assert quote == "CAD"


# ====================================================================
# Fix F: Bar query LIMIT constant
# ====================================================================


class TestBarQueryLimit:
    """Verify MAX_BARS_PER_QUERY exists and is reasonable."""

    def test_max_bars_constant_exists(self):
        from app.api.v1.research import MAX_BARS_PER_QUERY
        assert isinstance(MAX_BARS_PER_QUERY, int)
        assert MAX_BARS_PER_QUERY > 0

    def test_max_bars_not_too_large(self):
        """Should be bounded to prevent OOM — no more than 1M bars."""
        from app.api.v1.research import MAX_BARS_PER_QUERY
        assert MAX_BARS_PER_QUERY <= 1_000_000

    def test_max_bars_large_enough_for_mvp(self):
        """Should be at least 100K to cover reasonable backtests."""
        from app.api.v1.research import MAX_BARS_PER_QUERY
        assert MAX_BARS_PER_QUERY >= 100_000


# ====================================================================
# Fix E (bonus): Default book balances
# ====================================================================


class TestPaperOrderBookDefaults:
    """Verify paper order book defaults are forex-appropriate."""

    def test_default_usd_balance(self):
        book = PaperOrderBook()
        assert book.get_balance("USD") == Decimal("100000")

    def test_no_crypto_defaults(self):
        book = PaperOrderBook()
        assert book.get_balance("BTC") == Decimal("0")
        assert book.get_balance("ETH") == Decimal("0")
        assert book.get_balance("USDT") == Decimal("0")

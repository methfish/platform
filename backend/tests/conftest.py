"""
Shared test fixtures for the Pensy platform test suite.
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from uuid import uuid4

from app.config import Settings
from app.core.events import EventBus
from app.exchange.paper.adapter import PaperExchangeAdapter


@pytest.fixture
def settings():
    """Test settings with safe defaults."""
    return Settings(
        APP_ENV="development",
        LIVE_TRADING_ENABLED=False,
        DATABASE_URL="sqlite+aiosqlite:///",  # In-memory for tests
        MAX_ORDER_NOTIONAL=Decimal("10000"),
        MAX_ORDER_QUANTITY=Decimal("100"),
        MAX_POSITION_NOTIONAL=Decimal("50000"),
        MAX_DAILY_LOSS=Decimal("5000"),
        MAX_ORDERS_PER_MINUTE=30,
        PRICE_DEVIATION_THRESHOLD=Decimal("0.05"),
        SYMBOL_WHITELIST="BTCUSDT,ETHUSDT,SOLUSDT",
    )


@pytest.fixture
def event_bus():
    """Fresh event bus for each test."""
    return EventBus()


@pytest_asyncio.fixture
async def paper_adapter():
    """Paper exchange adapter with seeded balances and prices."""
    adapter = PaperExchangeAdapter(
        initial_balances={
            "USDT": Decimal("100000"),
            "BTC": Decimal("1"),
            "ETH": Decimal("10"),
        },
        commission_rate=Decimal("0.001"),
    )
    await adapter.connect()

    # Seed prices
    adapter.update_market_price("BTCUSDT", Decimal("49999"), Decimal("50001"), Decimal("50000"))
    adapter.update_market_price("ETHUSDT", Decimal("2999"), Decimal("3001"), Decimal("3000"))
    adapter.update_market_price("SOLUSDT", Decimal("99.9"), Decimal("100.1"), Decimal("100"))

    yield adapter
    await adapter.disconnect()

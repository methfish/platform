"""
Test data factories for creating domain objects.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.enums import OrderSide, OrderStatus, OrderType, TimeInForce, TradingMode


def make_order_dict(**overrides) -> dict:
    """Create order kwargs for testing."""
    defaults = {
        "id": uuid4(),
        "client_order_id": f"test-{uuid4().hex[:12]}",
        "exchange": "paper",
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "quantity": Decimal("0.1"),
        "price": Decimal("50000"),
        "time_in_force": TimeInForce.GTC.value,
        "status": OrderStatus.PENDING.value,
        "trading_mode": TradingMode.PAPER.value,
        "filled_quantity": Decimal("0"),
    }
    defaults.update(overrides)
    return defaults


def make_fill_dict(**overrides) -> dict:
    """Create fill kwargs for testing."""
    defaults = {
        "id": uuid4(),
        "order_id": uuid4(),
        "exchange_fill_id": f"fill-{uuid4().hex[:8]}",
        "quantity": Decimal("0.1"),
        "price": Decimal("50000"),
        "commission": Decimal("5"),
        "commission_asset": "USDT",
        "fill_time": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return defaults


def make_risk_context(**overrides) -> dict:
    """Create risk check context kwargs."""
    defaults = {
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY.value,
        "order_type": OrderType.LIMIT.value,
        "quantity": Decimal("0.1"),
        "price": Decimal("50000"),
        "last_price": Decimal("50000"),
        "bid_price": Decimal("49999"),
        "ask_price": Decimal("50001"),
        "current_position_quantity": Decimal("0"),
        "daily_realized_pnl": Decimal("0"),
        "kill_switch_active": False,
        "max_order_notional": Decimal("10000"),
        "max_order_quantity": Decimal("100"),
        "max_position_notional": Decimal("50000"),
        "max_daily_loss": Decimal("5000"),
        "max_orders_per_minute": 30,
        "price_deviation_threshold": Decimal("0.05"),
        "symbol_whitelist": {"BTCUSDT", "ETHUSDT", "SOLUSDT"},
    }
    defaults.update(overrides)
    return defaults

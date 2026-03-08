"""
Paper trading fill simulation engine.

Simulates order matching with configurable assumptions:
- Market orders fill immediately at last price with configurable slippage
- Limit orders fill when price crosses the limit
- Partial fills are supported
- Commission is configurable
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.enums import OrderSide, OrderType


@dataclass
class SimulatedFill:
    fill_id: str
    quantity: Decimal
    price: Decimal
    commission: Decimal
    commission_asset: str
    fill_time: datetime
    is_complete: bool  # True if order is fully filled


@dataclass
class PaperOrderState:
    exchange_order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Decimal | None
    filled_quantity: Decimal = Decimal("0")
    status: str = "NEW"
    created_at: datetime | None = None


class MatchingEngine:
    """
    Simple matching engine for paper trading.

    Assumptions documented here:
    - Market orders fill 100% at last price + slippage
    - Limit BUY fills when ask <= limit price
    - Limit SELL fills when bid >= limit price
    - Commission is flat rate (default 0.1% / 10 bps)
    - No partial fills for market orders
    - Limit orders fill fully when price crosses
    """

    def __init__(
        self,
        commission_rate: Decimal = Decimal("0.001"),
        slippage_bps: Decimal = Decimal("0.0005"),
    ):
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps

    def try_fill_market(
        self,
        order: PaperOrderState,
        last_price: Decimal,
        bid: Decimal | None = None,
        ask: Decimal | None = None,
    ) -> SimulatedFill | None:
        """Attempt to fill a market order immediately."""
        if order.order_type != OrderType.MARKET:
            return None

        if last_price <= 0:
            return None

        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = last_price * (Decimal("1") + self.slippage_bps)
            if ask and ask > 0:
                fill_price = ask * (Decimal("1") + self.slippage_bps)
        else:
            fill_price = last_price * (Decimal("1") - self.slippage_bps)
            if bid and bid > 0:
                fill_price = bid * (Decimal("1") - self.slippage_bps)

        remaining = order.quantity - order.filled_quantity
        commission = remaining * fill_price * self.commission_rate

        return SimulatedFill(
            fill_id=str(uuid4()),
            quantity=remaining,
            price=fill_price.quantize(Decimal("0.00000001")),
            commission=commission.quantize(Decimal("0.00000001")),
            commission_asset=self._get_commission_asset(order.symbol, order.side),
            fill_time=datetime.now(timezone.utc),
            is_complete=True,
        )

    def try_fill_limit(
        self,
        order: PaperOrderState,
        bid: Decimal,
        ask: Decimal,
    ) -> SimulatedFill | None:
        """Check if a limit order should fill given current prices."""
        if order.order_type != OrderType.LIMIT:
            return None

        if order.price is None:
            return None

        should_fill = False
        fill_price = order.price

        if order.side == OrderSide.BUY and ask > 0:
            # Buy limit fills when ask drops to or below limit price
            should_fill = ask <= order.price
            fill_price = min(order.price, ask)
        elif order.side == OrderSide.SELL and bid > 0:
            # Sell limit fills when bid rises to or above limit price
            should_fill = bid >= order.price
            fill_price = max(order.price, bid)

        if not should_fill:
            return None

        remaining = order.quantity - order.filled_quantity
        commission = remaining * fill_price * self.commission_rate

        return SimulatedFill(
            fill_id=str(uuid4()),
            quantity=remaining,
            price=fill_price.quantize(Decimal("0.00000001")),
            commission=commission.quantize(Decimal("0.00000001")),
            commission_asset=self._get_commission_asset(order.symbol, order.side),
            fill_time=datetime.now(timezone.utc),
            is_complete=True,
        )

    def _get_commission_asset(self, symbol: str, side: OrderSide) -> str:
        """Determine commission asset (simplified: always quote currency)."""
        # For pairs like BTCUSDT, commission is in USDT
        for quote in ["USDT", "USDC", "BUSD", "BTC", "ETH"]:
            if symbol.endswith(quote):
                return quote
        return "USDT"

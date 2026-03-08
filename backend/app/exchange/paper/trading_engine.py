"""Paper trading simulator - executes orders in memory without real money."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.models.order import Order, OrderFill
from app.models.position import Position
from app.exchange.models import TickerSnapshot

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """Simulates order execution and fills using current market prices."""

    def __init__(self, slippage_percent: Decimal = Decimal("0.01")):
        """
        Args:
            slippage_percent: Simulated slippage (0.01 = 0.01%)
        """
        self.slippage_percent = slippage_percent
        self._pending_orders: dict[UUID, Order] = {}

    async def execute_order(
        self,
        order: Order,
        current_price: Decimal,
    ) -> list[OrderFill]:
        """
        Execute a paper order using current market price.

        Args:
            order: Order to execute
            current_price: Current market price for fill calculation

        Returns:
            List of OrderFill objects (usually one for paper trading)
        """
        if order.order_type == "MARKET":
            # Market orders fill at current price + slippage
            fill_price = self._apply_slippage(current_price, order.side)
            return await self._create_fill(order, order.quantity, fill_price)
        elif order.order_type == "LIMIT":
            # LIMIT orders only fill if price is at or better than limit
            if self._price_acceptable(current_price, order.price, order.side):
                fill_price = min(current_price, order.price)
                return await self._create_fill(order, order.quantity, fill_price)
            else:
                # Order remains pending
                self._pending_orders[order.id] = order
                logger.debug(
                    f"LIMIT order {order.client_order_id} pending: "
                    f"{order.side} {order.quantity} @ {order.price}, "
                    f"current price: {current_price}"
                )
                return []
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

    async def check_pending_orders(
        self,
        symbol: str,
        current_price: Decimal,
    ) -> list[tuple[Order, list[OrderFill]]]:
        """
        Check if any pending LIMIT orders can be filled at current price.

        Args:
            symbol: Trading symbol
            current_price: Current market price

        Returns:
            List of (order, fills) tuples for orders that were filled
        """
        filled = []
        orders_to_remove = []

        for order_id, order in self._pending_orders.items():
            if order.symbol != symbol:
                continue

            if self._price_acceptable(current_price, order.price, order.side):
                fill_price = min(current_price, order.price)
                fills = await self._create_fill(order, order.quantity, fill_price)
                filled.append((order, fills))
                orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            del self._pending_orders[order_id]

        return filled

    async def cancel_order(self, order: Order) -> bool:
        """Cancel a pending order."""
        if order.id in self._pending_orders:
            del self._pending_orders[order.id]
            logger.info(f"Cancelled paper order {order.client_order_id}")
            return True
        return False

    # ========== PRIVATE METHODS ==========

    def _apply_slippage(self, price: Decimal, side: str) -> Decimal:
        """Apply simulated slippage to price for MARKET orders."""
        slippage = price * self.slippage_percent / Decimal("100")
        if side == "BUY":
            return price + slippage  # Buy slips up
        else:
            return price - slippage  # Sell slips down

    def _price_acceptable(
        self, current_price: Decimal, limit_price: Decimal, side: str
    ) -> bool:
        """Check if current price is acceptable for limit order."""
        if side == "BUY":
            return current_price <= limit_price
        else:  # SELL
            return current_price >= limit_price

    async def _create_fill(
        self,
        order: Order,
        fill_quantity: Decimal,
        fill_price: Decimal,
    ) -> list[OrderFill]:
        """
        Create OrderFill records for a paper trade.

        Args:
            order: Order being filled
            fill_quantity: Quantity to fill
            fill_price: Price to fill at

        Returns:
            List containing one OrderFill
        """
        # Calculate commission (0.1% for paper trading)
        commission_percent = Decimal("0.001")
        commission = fill_quantity * fill_price * commission_percent

        fill = OrderFill(
            order_id=order.id,
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
            commission_asset="USDT",
            fill_time=datetime.now(timezone.utc),
        )

        logger.info(
            f"Paper filled {order.side} {fill_quantity} {order.symbol} "
            f"@ {fill_price} (commission: {commission})"
        )

        return [fill]


class SimpleBalanceTracker:
    """Simple paper account balance tracking."""

    def __init__(self, initial_balance: Decimal = Decimal("10000")):
        """Initialize with starting balance."""
        self.balance = initial_balance
        self.reserves = Decimal("0")
        self.transactions: list[dict] = []

    def reserve_for_order(
        self,
        order_id: UUID,
        quantity: Decimal,
        price: Decimal,
    ) -> bool:
        """Reserve balance for a BUY order."""
        required = quantity * price
        if required <= self.balance - self.reserves:
            self.reserves += required
            self.transactions.append({
                "type": "reserve",
                "order_id": order_id,
                "amount": required,
                "timestamp": datetime.now(timezone.utc),
            })
            return True
        return False

    def release_reserve(self, order_id: UUID, amount: Decimal) -> None:
        """Release reserved balance (for cancelled orders)."""
        self.reserves = max(Decimal("0"), self.reserves - amount)

    def apply_fill(
        self,
        order_id: UUID,
        side: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
    ) -> None:
        """Apply a fill to the balance."""
        total_cost = quantity * price + commission

        if side == "BUY":
            self.balance -= total_cost
            self.reserves = max(Decimal("0"), self.reserves - total_cost)
        else:  # SELL
            self.balance += quantity * price - commission

        self.transactions.append({
            "type": "fill",
            "order_id": order_id,
            "side": side,
            "quantity": quantity,
            "price": price,
            "commission": commission,
            "timestamp": datetime.now(timezone.utc),
        })

    def get_available_balance(self) -> Decimal:
        """Get available (unreserved) balance."""
        return self.balance - self.reserves

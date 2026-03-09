"""
Fill handler for processing exchange fill events.

Processes fill notifications from the exchange adapter, updates order
state (filled_quantity, avg_fill_price, status), creates OrderFill
records, and emits OrderFilled events.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.core.events import EventBus, OrderFilled, OrderStatusChanged
from app.models.order import Order, OrderFill
from app.oms.state_machine import validate_transition

logger = logging.getLogger(__name__)


class FillHandler:
    """
    Processes fill events from the exchange adapter.

    Responsible for:
        - Updating order filled_quantity and avg_fill_price.
        - Creating immutable OrderFill records.
        - Transitioning order status (PARTIALLY_FILLED / FILLED).
        - Emitting OrderFilled events.
        - Delegating position updates to a position tracker (if provided).

    Args:
        event_bus: The async event bus for domain events.
        position_tracker: Optional position tracker for updating positions on fills.
    """

    def __init__(
        self,
        event_bus: EventBus,
        position_tracker: Any = None,
    ) -> None:
        self.event_bus = event_bus
        self.position_tracker = position_tracker

    async def process_fill(
        self,
        order: Order,
        fill_quantity: Decimal,
        fill_price: Decimal,
        session: AsyncSession,
        commission: Decimal = Decimal("0"),
        commission_asset: Optional[str] = None,
        exchange_fill_id: Optional[str] = None,
        fill_time: Optional[datetime] = None,
    ) -> OrderFill:
        """
        Process a single fill event for an order.

        Args:
            order: The order being filled.
            fill_quantity: Quantity filled in this execution.
            fill_price: Price at which this fill executed.
            session: SQLAlchemy async session.
            commission: Commission charged for this fill.
            commission_asset: Asset in which commission was charged.
            exchange_fill_id: Exchange-assigned fill/trade ID.
            fill_time: Time of the fill (defaults to now).

        Returns:
            The created OrderFill record.
        """
        if fill_time is None:
            fill_time = datetime.now(timezone.utc)

        # Create the fill record
        order_fill = OrderFill(
            order_id=order.id,
            exchange_fill_id=exchange_fill_id,
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
            commission_asset=commission_asset,
            fill_time=fill_time,
        )
        session.add(order_fill)

        # Update order aggregate fill data
        previous_filled = order.filled_quantity or Decimal("0")
        new_filled = previous_filled + fill_quantity

        # Weighted average fill price
        if previous_filled == Decimal("0"):
            new_avg_price = fill_price
        else:
            old_avg = order.avg_fill_price or Decimal("0")
            new_avg_price = (
                (old_avg * previous_filled) + (fill_price * fill_quantity)
            ) / new_filled

        order.filled_quantity = new_filled
        order.avg_fill_price = new_avg_price

        # Determine new status
        if new_filled >= order.quantity:
            target_status = OrderStatus.FILLED
            order.filled_at = fill_time
        else:
            target_status = OrderStatus.PARTIALLY_FILLED

        # Transition if status is changing
        current_status = OrderStatus(order.status)
        if current_status != target_status:
            validate_transition(current_status, target_status)
            old_status = order.status
            order.status = target_status.value

            await session.flush()

            logger.info(
                "Order fill processed",
                extra={
                    "order_id": str(order.id),
                    "fill_qty": str(fill_quantity),
                    "fill_price": str(fill_price),
                    "total_filled": str(new_filled),
                    "status": target_status.value,
                },
            )

            await self.event_bus.publish(
                OrderStatusChanged(
                    order_id=order.id,
                    old_status=old_status,
                    new_status=target_status.value,
                    reason=f"Fill: {fill_quantity}@{fill_price}",
                )
            )
        else:
            await session.flush()

        # Emit fill event
        await self.event_bus.publish(
            OrderFilled(
                order_id=order.id,
                fill_id=order_fill.id,
                symbol=order.symbol,
                side=order.side,
                quantity=fill_quantity,
                price=fill_price,
                commission=commission,
            )
        )

        # Update positions if tracker is available
        if self.position_tracker is not None:
            try:
                await self.position_tracker.update_on_fill(
                    session=session,
                    exchange=order.exchange,
                    symbol=order.symbol,
                    side=order.side,
                    fill_quantity=fill_quantity,
                    fill_price=fill_price,
                    commission=commission,
                    trading_mode=order.trading_mode,
                )
            except Exception:
                logger.exception(
                    "Position tracker update failed",
                    extra={"order_id": str(order.id)},
                )

        return order_fill

    async def process_fill_by_order_id(
        self,
        order_id: UUID,
        fill_quantity: Decimal,
        fill_price: Decimal,
        session: AsyncSession,
        commission: Decimal = Decimal("0"),
        commission_asset: Optional[str] = None,
        exchange_fill_id: Optional[str] = None,
        fill_time: Optional[datetime] = None,
    ) -> OrderFill:
        """
        Process a fill event by order ID lookup.

        Args:
            order_id: The UUID of the order.
            fill_quantity: Quantity filled.
            fill_price: Fill price.
            session: SQLAlchemy async session.
            commission: Commission charged.
            commission_asset: Commission asset.
            exchange_fill_id: Exchange fill ID.
            fill_time: Time of fill.

        Returns:
            The created OrderFill record.

        Raises:
            ValueError: If the order is not found.
        """
        order = await session.get(Order, order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        return await self.process_fill(
            order=order,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            session=session,
            commission=commission,
            commission_asset=commission_asset,
            exchange_fill_id=exchange_fill_id,
            fill_time=fill_time,
        )

    async def process_fill_by_client_order_id(
        self,
        client_order_id: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        session: AsyncSession,
        commission: Decimal = Decimal("0"),
        commission_asset: Optional[str] = None,
        exchange_fill_id: Optional[str] = None,
        fill_time: Optional[datetime] = None,
    ) -> OrderFill:
        """
        Process a fill event by client_order_id lookup.

        Args:
            client_order_id: The client-assigned order ID.
            fill_quantity: Quantity filled.
            fill_price: Fill price.
            session: SQLAlchemy async session.
            commission: Commission charged.
            commission_asset: Commission asset.
            exchange_fill_id: Exchange fill ID.
            fill_time: Time of fill.

        Returns:
            The created OrderFill record.

        Raises:
            ValueError: If the order is not found.
        """
        stmt = select(Order).where(Order.client_order_id == client_order_id)
        result = await session.execute(stmt)
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError(f"Order not found for client_order_id: {client_order_id}")

        return await self.process_fill(
            order=order,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            session=session,
            commission=commission,
            commission_asset=commission_asset,
            exchange_fill_id=exchange_fill_id,
            fill_time=fill_time,
        )

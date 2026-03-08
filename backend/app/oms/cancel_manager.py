"""
Cancel manager for handling order cancellation flow.

Validates that an order is in a cancellable state, transitions it
to CANCEL_PENDING, sends the cancel request to the exchange, and
handles the exchange response.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.core.events import EventBus, OrderStatusChanged
from app.core.exceptions import InvalidStateTransition
from app.exchange.base import ExchangeAdapter
from app.models.order import Order
from app.oms.state_machine import validate_transition

logger = logging.getLogger(__name__)

# Statuses from which an order can be cancelled
CANCELLABLE_STATUSES = {
    OrderStatus.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED,
}


class CancelManager:
    """
    Manages the order cancellation lifecycle.

    Handles:
        - Validating that an order is in a cancellable state.
        - Transitioning the order to CANCEL_PENDING.
        - Sending the cancel request to the exchange adapter.
        - Processing the exchange cancel response.

    Args:
        exchange_adapter: The exchange adapter for sending cancel requests.
        event_bus: The async event bus for domain events.
    """

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        event_bus: EventBus,
    ) -> None:
        self.exchange_adapter = exchange_adapter
        self.event_bus = event_bus

    async def cancel_order(
        self,
        order: Order,
        session: AsyncSession,
    ) -> Order:
        """
        Execute the full cancel flow for an order.

        Steps:
            1. Validate that the order is in a cancellable state.
            2. Transition to CANCEL_PENDING and persist.
            3. Send cancel request to exchange.
            4. Handle exchange response (CANCELLED or revert).

        Args:
            order: The order to cancel.
            session: SQLAlchemy async session.

        Returns:
            The updated Order instance.

        Raises:
            InvalidStateTransition: If the order cannot be cancelled.
        """
        current_status = OrderStatus(order.status)

        if current_status not in CANCELLABLE_STATUSES:
            raise InvalidStateTransition(
                current_status.value,
                OrderStatus.CANCEL_PENDING.value,
            )

        # Transition to CANCEL_PENDING
        await self._transition(
            order=order,
            target_status=OrderStatus.CANCEL_PENDING,
            session=session,
            reason="Cancel requested",
        )

        # Send cancel to exchange
        try:
            cancel_result = await self.exchange_adapter.cancel_order(
                symbol=order.symbol,
                exchange_order_id=order.exchange_order_id,
                client_order_id=order.client_order_id,
            )

            if cancel_result.success:
                order.cancelled_at = datetime.now(timezone.utc)
                await self._transition(
                    order=order,
                    target_status=OrderStatus.CANCELLED,
                    session=session,
                    reason="Cancelled by exchange",
                )
            else:
                # Exchange rejected the cancel - log but leave in CANCEL_PENDING.
                # The order may fill naturally, which the state machine allows.
                logger.warning(
                    "Exchange cancel rejected",
                    extra={
                        "order_id": str(order.id),
                        "message": cancel_result.message,
                    },
                )

        except Exception as exc:
            # Network or adapter error - leave in CANCEL_PENDING.
            # A reconciliation pass will resolve the final state.
            logger.exception(
                "Cancel request failed",
                extra={
                    "order_id": str(order.id),
                    "error": str(exc),
                },
            )

        return order

    def is_cancellable(self, order: Order) -> bool:
        """
        Check whether an order is in a state that allows cancellation.

        Args:
            order: The order to check.

        Returns:
            True if the order can be cancelled.
        """
        try:
            current_status = OrderStatus(order.status)
            return current_status in CANCELLABLE_STATUSES
        except ValueError:
            return False

    async def _transition(
        self,
        order: Order,
        target_status: OrderStatus,
        session: AsyncSession,
        reason: str = "",
    ) -> None:
        """
        Transition order status with persistence and event emission.

        Args:
            order: The order to transition.
            target_status: The target status.
            session: SQLAlchemy async session.
            reason: Reason for the transition.
        """
        current_status = OrderStatus(order.status)
        validate_transition(current_status, target_status)

        old_status = order.status
        order.status = target_status.value
        await session.flush()

        logger.info(
            "Cancel manager: order state transition",
            extra={
                "order_id": str(order.id),
                "from": old_status,
                "to": target_status.value,
                "reason": reason,
            },
        )

        await self.event_bus.publish(
            OrderStatusChanged(
                order_id=order.id,
                old_status=old_status,
                new_status=target_status.value,
                reason=reason,
            )
        )

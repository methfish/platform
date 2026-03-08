"""
Order Management Service - central orchestrator for order lifecycle.

Coordinates order creation, risk validation, exchange submission,
and state transitions. All state transitions are persisted to the
database BEFORE events are emitted to the event bus.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from app.core.events import (
    EventBus,
    OrderCreated,
    OrderStatusChanged,
    RiskCheckCompleted,
)
from app.core.exceptions import OrderNotFound, RiskCheckFailed
from app.exchange.base import ExchangeAdapter
from app.models.order import Order
from app.oms.cancel_manager import CancelManager
from app.oms.state_machine import validate_transition
from app.oms.validator import validate_order

logger = logging.getLogger(__name__)


class OrderManagementService:
    """
    Manages the full order lifecycle: creation, risk evaluation,
    exchange submission, cancellation, and querying.

    Args:
        exchange_adapter: The exchange adapter for order routing.
        risk_engine: The risk engine for pre-trade checks.
        event_bus: The async event bus for publishing domain events.
    """

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        risk_engine: Any,  # RiskEngine - forward reference to avoid circular import
        event_bus: EventBus,
    ) -> None:
        self.exchange_adapter = exchange_adapter
        self.risk_engine = risk_engine
        self.event_bus = event_bus
        self.cancel_manager = CancelManager(exchange_adapter, event_bus)

    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        strategy_id: Optional[UUID] = None,
        client_order_id: Optional[str] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        session: AsyncSession | None = None,
        risk_context: Any = None,
    ) -> Order:
        """
        Submit a new order through the full lifecycle pipeline.

        Steps:
            1. Validate order parameters.
            2. Create the order in PENDING state and persist.
            3. Run risk checks.
            4. Transition to APPROVED or REJECTED based on risk result.
            5. If approved, submit to exchange.
            6. Transition to SUBMITTED (or FAILED / EXCHANGE_REJECTED).

        Args:
            symbol: Trading pair (e.g. BTCUSDT).
            side: BUY or SELL.
            order_type: MARKET, LIMIT, etc.
            quantity: Order quantity.
            price: Limit price (required for LIMIT orders).
            strategy_id: Optional strategy reference.
            client_order_id: Optional idempotency key (generated if absent).
            time_in_force: Order time-in-force instruction.
            session: SQLAlchemy async session for persistence.
            risk_context: Optional context data for risk checks.

        Returns:
            The Order model instance in its current state.

        Raises:
            ValueError: If order parameters fail validation.
            RiskCheckFailed: If risk checks reject the order.
        """
        if session is None:
            raise ValueError("Database session is required for submit_order.")

        # Step 1: Validate parameters
        validation_errors = validate_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
        )
        if validation_errors:
            raise ValueError(f"Order validation failed: {'; '.join(validation_errors)}")

        # Step 2: Create order in PENDING state
        if client_order_id is None:
            client_order_id = str(uuid4())

        order = Order(
            client_order_id=client_order_id,
            exchange=self.exchange_adapter.exchange_name,
            symbol=symbol.upper().strip(),
            side=side.value,
            order_type=order_type.value,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force.value,
            status=OrderStatus.PENDING.value,
            strategy_id=strategy_id,
            filled_quantity=Decimal("0"),
        )
        session.add(order)
        await session.flush()

        logger.info(
            "Order created",
            extra={
                "order_id": str(order.id),
                "client_order_id": client_order_id,
                "symbol": symbol,
                "side": side.value,
                "type": order_type.value,
                "quantity": str(quantity),
                "price": str(price) if price else None,
            },
        )

        await self.event_bus.publish(
            OrderCreated(
                order_id=order.id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side.value,
                order_type=order_type.value,
                quantity=quantity,
                price=price,
            )
        )

        # Step 3: Run risk checks
        risk_result = await self.risk_engine.evaluate_order(order, risk_context)

        await self.event_bus.publish(
            RiskCheckCompleted(
                order_id=order.id,
                passed=risk_result.passed,
                failed_checks=risk_result.failed_checks,
            )
        )

        # Step 4: Transition based on risk result
        if not risk_result.passed:
            await self._transition_order(
                order=order,
                target_status=OrderStatus.REJECTED,
                session=session,
                reason=f"Risk check failed: {', '.join(risk_result.failed_checks)}",
            )
            order.reject_reason = f"Risk check failed: {', '.join(risk_result.failed_checks)}"
            await session.flush()
            raise RiskCheckFailed(
                [
                    {"check_name": r.check_name, "message": r.message}
                    for r in risk_result.results
                    if r.result.value == "FAIL"
                ]
            )

        # Transition to APPROVED
        await self._transition_order(
            order=order,
            target_status=OrderStatus.APPROVED,
            session=session,
            reason="Risk checks passed",
        )

        # Step 5: Submit to exchange
        try:
            exchange_result = await self.exchange_adapter.place_order(
                symbol=order.symbol,
                side=OrderSide(order.side),
                order_type=OrderType(order.order_type),
                quantity=order.quantity,
                price=order.price,
                client_order_id=order.client_order_id,
                time_in_force=TimeInForce(order.time_in_force),
            )

            if exchange_result.success:
                order.exchange_order_id = exchange_result.exchange_order_id
                order.submitted_at = datetime.now(timezone.utc)
                await self._transition_order(
                    order=order,
                    target_status=OrderStatus.SUBMITTED,
                    session=session,
                    reason="Submitted to exchange",
                )
            else:
                order.reject_reason = exchange_result.message
                await self._transition_order(
                    order=order,
                    target_status=OrderStatus.FAILED,
                    session=session,
                    reason=f"Exchange submission failed: {exchange_result.message}",
                )

        except Exception as exc:
            logger.exception(
                "Exchange submission error",
                extra={"order_id": str(order.id), "error": str(exc)},
            )
            order.reject_reason = str(exc)
            await self._transition_order(
                order=order,
                target_status=OrderStatus.FAILED,
                session=session,
                reason=f"Exchange error: {exc}",
            )

        return order

    async def cancel_order(
        self,
        order_id: UUID,
        session: AsyncSession,
    ) -> Order:
        """
        Cancel an open order.

        Args:
            order_id: The order ID to cancel.
            session: SQLAlchemy async session.

        Returns:
            The updated Order model instance.

        Raises:
            OrderNotFound: If the order does not exist.
        """
        order = await session.get(Order, order_id)
        if order is None:
            raise OrderNotFound(str(order_id))

        return await self.cancel_manager.cancel_order(order, session)

    async def get_order(
        self,
        order_id: UUID,
        session: AsyncSession,
    ) -> Order:
        """
        Retrieve a single order by ID.

        Args:
            order_id: The order ID.
            session: SQLAlchemy async session.

        Returns:
            The Order model instance.

        Raises:
            OrderNotFound: If the order does not exist.
        """
        order = await session.get(Order, order_id)
        if order is None:
            raise OrderNotFound(str(order_id))
        return order

    async def get_orders(
        self,
        filters: Optional[dict[str, Any]] = None,
        session: AsyncSession | None = None,
    ) -> list[Order]:
        """
        Query orders with optional filters.

        Supported filter keys:
            - symbol: str
            - side: str
            - status: str
            - strategy_id: UUID
            - trading_mode: str
            - limit: int (default 100)
            - offset: int (default 0)

        Args:
            filters: Dict of filter key-value pairs.
            session: SQLAlchemy async session.

        Returns:
            List of matching Order instances.
        """
        if session is None:
            raise ValueError("Database session is required for get_orders.")

        filters = filters or {}
        stmt = select(Order)

        if "symbol" in filters:
            stmt = stmt.where(Order.symbol == filters["symbol"])
        if "side" in filters:
            stmt = stmt.where(Order.side == filters["side"])
        if "status" in filters:
            stmt = stmt.where(Order.status == filters["status"])
        if "strategy_id" in filters:
            stmt = stmt.where(Order.strategy_id == filters["strategy_id"])
        if "trading_mode" in filters:
            stmt = stmt.where(Order.trading_mode == filters["trading_mode"])

        stmt = stmt.order_by(Order.created_at.desc())
        stmt = stmt.limit(filters.get("limit", 100))
        stmt = stmt.offset(filters.get("offset", 0))

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _transition_order(
        self,
        order: Order,
        target_status: OrderStatus,
        session: AsyncSession,
        reason: str = "",
    ) -> None:
        """
        Transition an order to a new status using the state machine.

        Persists the change to the database before emitting the event.

        Args:
            order: The order to transition.
            target_status: The target OrderStatus.
            session: SQLAlchemy async session.
            reason: Human-readable reason for the transition.
        """
        current_status = OrderStatus(order.status)
        validate_transition(current_status, target_status)

        old_status = order.status
        order.status = target_status.value
        await session.flush()

        logger.info(
            "Order state transition",
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

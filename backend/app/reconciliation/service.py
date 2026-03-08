"""
Reconciliation service - compares internal state vs exchange state.

Detects discrepancies in positions, balances, and open orders.
Generates break reports and emits alerts for severe mismatches.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    OrderStatus,
    ReconciliationBreakType,
    ReconciliationStatus,
)
from app.core.events import EventBus, ReconciliationCompleted, AlertTriggered
from app.exchange.base import ExchangeAdapter
from app.models.order import Order
from app.models.position import Position
from app.models.reconciliation import ReconciliationBreak, ReconciliationRun

logger = logging.getLogger(__name__)

# Tolerance for decimal comparison
TOLERANCE = Decimal("0.00001")


class ReconciliationService:
    """
    Compares internal state against exchange state.

    Checks:
    1. Open orders: internal vs exchange
    2. Positions: internal quantities vs exchange positions
    3. Balances: internal tracking vs exchange balances
    """

    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        event_bus: EventBus,
    ):
        self._adapter = exchange_adapter
        self._event_bus = event_bus

    async def run_reconciliation(
        self,
        session: AsyncSession,
        run_type: str = "MANUAL",
        trading_mode: str = "PAPER",
    ) -> ReconciliationRun:
        """Execute a full reconciliation run."""
        now = datetime.now(timezone.utc)
        run = ReconciliationRun(
            exchange=self._adapter.exchange_name,
            run_type=run_type,
            status=ReconciliationStatus.RUNNING.value,
            started_at=now,
        )
        session.add(run)
        await session.flush()

        breaks: list[ReconciliationBreak] = []

        try:
            # 1. Reconcile open orders
            order_breaks = await self._reconcile_orders(session, run, trading_mode)
            breaks.extend(order_breaks)

            # 2. Reconcile positions
            position_breaks = await self._reconcile_positions(session, run, trading_mode)
            breaks.extend(position_breaks)

            # 3. Reconcile balances
            balance_breaks = await self._reconcile_balances(session, run)
            breaks.extend(balance_breaks)

            run.breaks_found = len(breaks)
            run.status = ReconciliationStatus.COMPLETED.value
            run.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Reconciliation failed: {e}")
            run.status = ReconciliationStatus.FAILED.value
            run.completed_at = datetime.now(timezone.utc)

        await session.flush()

        # Emit events
        await self._event_bus.publish(ReconciliationCompleted(
            exchange=self._adapter.exchange_name,
            breaks_found=len(breaks),
            run_id=run.id,
        ))

        if breaks:
            await self._event_bus.publish(AlertTriggered(
                severity="WARNING",
                source="reconciliation",
                message=f"Reconciliation found {len(breaks)} breaks",
                details={"run_id": str(run.id), "break_count": len(breaks)},
            ))

        logger.info(
            f"Reconciliation completed: {len(breaks)} breaks found "
            f"(orders: {len(order_breaks) if 'order_breaks' in dir() else '?'}, "
            f"positions: {len(position_breaks) if 'position_breaks' in dir() else '?'})"
        )

        return run

    async def _reconcile_orders(
        self,
        session: AsyncSession,
        run: ReconciliationRun,
        trading_mode: str,
    ) -> list[ReconciliationBreak]:
        """Compare internal open orders vs exchange open orders."""
        breaks = []

        # Get internal open orders
        stmt = select(Order).where(
            Order.exchange == self._adapter.exchange_name,
            Order.trading_mode == trading_mode,
            Order.status.in_([
                OrderStatus.SUBMITTED.value,
                OrderStatus.PARTIALLY_FILLED.value,
            ]),
        )
        result = await session.execute(stmt)
        internal_orders = {o.client_order_id: o for o in result.scalars().all()}

        # Get exchange open orders
        exchange_orders = await self._adapter.get_open_orders()
        exchange_order_map = {o.client_order_id: o for o in exchange_orders if o.client_order_id}

        # Find orders in internal but not on exchange
        for coid, internal in internal_orders.items():
            if coid not in exchange_order_map:
                brk = ReconciliationBreak(
                    run_id=run.id,
                    break_type=ReconciliationBreakType.MISSING_ORDER.value,
                    symbol=internal.symbol,
                    internal_value={"client_order_id": coid, "status": internal.status},
                    exchange_value=None,
                )
                session.add(brk)
                breaks.append(brk)

        # Find orders on exchange but not in internal
        for coid, ext in exchange_order_map.items():
            if coid not in internal_orders:
                brk = ReconciliationBreak(
                    run_id=run.id,
                    break_type=ReconciliationBreakType.UNKNOWN_ORDER.value,
                    symbol=ext.symbol,
                    internal_value=None,
                    exchange_value={"client_order_id": coid, "status": ext.status},
                )
                session.add(brk)
                breaks.append(brk)

        return breaks

    async def _reconcile_positions(
        self,
        session: AsyncSession,
        run: ReconciliationRun,
        trading_mode: str,
    ) -> list[ReconciliationBreak]:
        """Compare internal positions vs exchange positions."""
        breaks = []

        # Get internal positions
        stmt = select(Position).where(
            Position.exchange == self._adapter.exchange_name,
            Position.trading_mode == trading_mode,
            Position.quantity > 0,
        )
        result = await session.execute(stmt)
        internal_positions = {p.symbol: p for p in result.scalars().all()}

        # Get exchange positions
        exchange_positions = await self._adapter.get_positions()
        exchange_pos_map = {p.symbol: p for p in exchange_positions}

        all_symbols = set(internal_positions.keys()) | set(exchange_pos_map.keys())

        for symbol in all_symbols:
            internal = internal_positions.get(symbol)
            external = exchange_pos_map.get(symbol)

            internal_qty = internal.quantity if internal else Decimal("0")
            external_qty = external.quantity if external else Decimal("0")

            if abs(internal_qty - external_qty) > TOLERANCE:
                brk = ReconciliationBreak(
                    run_id=run.id,
                    break_type=ReconciliationBreakType.POSITION_MISMATCH.value,
                    symbol=symbol,
                    internal_value={"quantity": str(internal_qty)},
                    exchange_value={"quantity": str(external_qty)},
                )
                session.add(brk)
                breaks.append(brk)

        return breaks

    async def _reconcile_balances(
        self,
        session: AsyncSession,
        run: ReconciliationRun,
    ) -> list[ReconciliationBreak]:
        """Compare internal balance tracking vs exchange balances."""
        # For v1, just log exchange balances without internal comparison
        # since we don't track balances separately from positions yet
        try:
            balances = await self._adapter.get_balances()
            logger.info(
                f"Exchange balances: "
                + ", ".join(f"{b.asset}={b.total}" for b in balances[:5])
            )
        except Exception as e:
            logger.warning(f"Could not fetch exchange balances: {e}")

        return []

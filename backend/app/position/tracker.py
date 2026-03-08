"""
Position tracker - maintains real-time position state.

Updates positions based on fill events. Each position is unique per
(exchange, symbol, trading_mode). Positions are persisted to PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderSide, PositionSide
from app.models.position import Position

logger = logging.getLogger(__name__)


class PositionTracker:
    """
    Tracks positions and updates them on fills.

    Position math:
    - BUY fill: increases LONG position (or reduces SHORT)
    - SELL fill: increases SHORT position (or reduces LONG)
    - Average entry price uses weighted average for additions
    - Realized PnL computed on position reductions
    """

    async def update_on_fill(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        side: str,
        fill_quantity: Decimal,
        fill_price: Decimal,
        commission: Decimal,
        trading_mode: str,
    ) -> Position:
        """
        Update position after a fill.

        Args:
            session: DB session
            exchange: Exchange name
            symbol: Trading pair
            side: BUY or SELL
            fill_quantity: Quantity filled
            fill_price: Fill price
            commission: Commission paid
            trading_mode: PAPER or LIVE

        Returns:
            Updated Position model
        """
        position = await self._get_or_create_position(
            session, exchange, symbol, trading_mode
        )

        if side == OrderSide.BUY.value:
            position = self._apply_buy(position, fill_quantity, fill_price, commission)
        else:
            position = self._apply_sell(position, fill_quantity, fill_price, commission)

        position.updated_at = datetime.now(timezone.utc)
        await session.flush()

        logger.info(
            f"Position updated: {symbol} {position.side} "
            f"qty={position.quantity} avg={position.avg_entry_price} "
            f"realized_pnl={position.realized_pnl}"
        )

        return position

    def _apply_buy(
        self,
        position: Position,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
    ) -> Position:
        """Apply a BUY fill to position."""
        current_qty = position.quantity
        current_side = position.side

        if current_side == PositionSide.FLAT.value or current_side == PositionSide.LONG.value:
            # Adding to long or opening new long
            new_qty = current_qty + quantity
            if new_qty > 0:
                # Weighted average entry price
                total_cost = (current_qty * position.avg_entry_price) + (quantity * price)
                position.avg_entry_price = total_cost / new_qty
            position.quantity = new_qty
            position.side = PositionSide.LONG.value
            if current_qty == 0:
                position.opened_at = datetime.now(timezone.utc)

        elif current_side == PositionSide.SHORT.value:
            # Reducing short position
            close_qty = min(quantity, current_qty)
            remaining_buy = quantity - close_qty

            # Realized PnL from closing short
            pnl = close_qty * (position.avg_entry_price - price)
            position.realized_pnl += pnl

            new_qty = current_qty - close_qty
            if new_qty <= 0 and remaining_buy > 0:
                # Flipped to long
                position.quantity = remaining_buy
                position.avg_entry_price = price
                position.side = PositionSide.LONG.value
            elif new_qty <= 0:
                position.quantity = Decimal("0")
                position.side = PositionSide.FLAT.value
                position.avg_entry_price = Decimal("0")
            else:
                position.quantity = new_qty

        position.total_commission += commission
        return position

    def _apply_sell(
        self,
        position: Position,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
    ) -> Position:
        """Apply a SELL fill to position."""
        current_qty = position.quantity
        current_side = position.side

        if current_side == PositionSide.FLAT.value or current_side == PositionSide.SHORT.value:
            # Adding to short or opening new short
            new_qty = current_qty + quantity
            if new_qty > 0:
                total_cost = (current_qty * position.avg_entry_price) + (quantity * price)
                position.avg_entry_price = total_cost / new_qty
            position.quantity = new_qty
            position.side = PositionSide.SHORT.value
            if current_qty == 0:
                position.opened_at = datetime.now(timezone.utc)

        elif current_side == PositionSide.LONG.value:
            # Reducing long position
            close_qty = min(quantity, current_qty)
            remaining_sell = quantity - close_qty

            # Realized PnL from closing long
            pnl = close_qty * (price - position.avg_entry_price)
            position.realized_pnl += pnl

            new_qty = current_qty - close_qty
            if new_qty <= 0 and remaining_sell > 0:
                # Flipped to short
                position.quantity = remaining_sell
                position.avg_entry_price = price
                position.side = PositionSide.SHORT.value
            elif new_qty <= 0:
                position.quantity = Decimal("0")
                position.side = PositionSide.FLAT.value
                position.avg_entry_price = Decimal("0")
            else:
                position.quantity = new_qty

        position.total_commission += commission
        return position

    async def _get_or_create_position(
        self,
        session: AsyncSession,
        exchange: str,
        symbol: str,
        trading_mode: str,
    ) -> Position:
        """Get existing position or create a new flat one."""
        stmt = select(Position).where(
            Position.exchange == exchange,
            Position.symbol == symbol,
            Position.trading_mode == trading_mode,
        )
        result = await session.execute(stmt)
        position = result.scalar_one_or_none()

        if position is None:
            position = Position(
                exchange=exchange,
                symbol=symbol,
                side=PositionSide.FLAT.value,
                quantity=Decimal("0"),
                avg_entry_price=Decimal("0"),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                total_commission=Decimal("0"),
                trading_mode=trading_mode,
            )
            session.add(position)
            await session.flush()

        return position

    async def get_all_positions(
        self,
        session: AsyncSession,
        trading_mode: str | None = None,
        exchange: str | None = None,
    ) -> list[Position]:
        """Get all non-flat positions."""
        stmt = select(Position).where(Position.side != PositionSide.FLAT.value)
        if trading_mode:
            stmt = stmt.where(Position.trading_mode == trading_mode)
        if exchange:
            stmt = stmt.where(Position.exchange == exchange)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def update_unrealized_pnl(
        self,
        position: Position,
        mark_price: Decimal,
    ) -> Decimal:
        """Calculate and update unrealized PnL for a position."""
        if position.quantity <= 0 or position.side == PositionSide.FLAT.value:
            position.unrealized_pnl = Decimal("0")
            return Decimal("0")

        if position.side == PositionSide.LONG.value:
            pnl = position.quantity * (mark_price - position.avg_entry_price)
        else:
            pnl = position.quantity * (position.avg_entry_price - mark_price)

        position.unrealized_pnl = pnl
        return pnl

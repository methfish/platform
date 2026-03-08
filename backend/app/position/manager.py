"""Position manager - tracks positions and calculates PnL."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.position import Position
from app.models.order import Order, OrderFill

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages position tracking and PnL calculation."""

    @staticmethod
    async def update_position_from_fill(
        session: AsyncSession,
        order: Order,
        fill: OrderFill,
    ) -> Position:
        """
        Update or create a position from a fill.

        Args:
            session: Database session
            order: Order that was filled
            fill: OrderFill record

        Returns:
            Updated Position object
        """
        symbol = order.symbol

        # Get or create position
        result = await session.execute(
            select(Position).where(Position.symbol == symbol)
        )
        position = result.scalar_one_or_none()

        if not position:
            position = Position(
                symbol=symbol,
                quantity=Decimal("0"),
                side="FLAT",
                avg_entry_price=Decimal("0"),
                trading_mode=order.trading_mode,
            )
            session.add(position)

        # Update position based on fill
        old_qty = position.quantity
        old_side = position.side

        if order.side == "BUY":
            if position.side == "SHORT":
                # Closing short position
                position.quantity -= fill.quantity
                if position.quantity == 0:
                    position.side = "FLAT"
                # Calculate realized PnL
                position.realized_pnl += (position.avg_entry_price - fill.price) * fill.quantity
            else:
                # Adding to long position
                total_cost = (position.avg_entry_price * old_qty) + (fill.price * fill.quantity)
                position.quantity += fill.quantity
                position.avg_entry_price = total_cost / position.quantity
                position.side = "LONG"
        else:  # SELL
            if position.side == "LONG":
                # Closing long position
                position.quantity -= fill.quantity
                if position.quantity == 0:
                    position.side = "FLAT"
                # Calculate realized PnL
                position.realized_pnl += (fill.price - position.avg_entry_price) * fill.quantity
            else:
                # Adding to short position
                total_cost = (position.avg_entry_price * old_qty) + (fill.price * fill.quantity)
                position.quantity = -abs(position.quantity + fill.quantity)
                position.avg_entry_price = total_cost / abs(position.quantity)
                position.side = "SHORT"

        position.updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Updated position {symbol}: "
            f"{old_side} {old_qty} → {position.side} {position.quantity} "
            f"@ {position.avg_entry_price:.4f}, "
            f"realized_pnl={position.realized_pnl:.2f}"
        )

        await session.flush()
        return position

    @staticmethod
    async def calculate_unrealized_pnl(
        position: Position,
        current_price: Decimal,
    ) -> Decimal:
        """Calculate unrealized PnL for a position."""
        if position.side == "FLAT" or position.quantity == 0:
            return Decimal("0")

        price_diff = current_price - position.avg_entry_price
        return price_diff * abs(position.quantity)

    @staticmethod
    async def calculate_roi_percent(
        position: Position,
        current_price: Decimal,
    ) -> float:
        """Calculate ROI percentage for a position."""
        if position.quantity == 0 or position.avg_entry_price == 0:
            return 0.0

        if position.side == "LONG":
            roi = (current_price - position.avg_entry_price) / position.avg_entry_price
        else:  # SHORT
            roi = (position.avg_entry_price - current_price) / position.avg_entry_price

        return float(roi * Decimal("100"))

    @staticmethod
    async def close_position(
        session: AsyncSession,
        position: Position,
        close_price: Decimal,
    ) -> Decimal:
        """
        Close a position entirely.

        Args:
            session: Database session
            position: Position to close
            close_price: Price to close at

        Returns:
            Realized PnL from closing
        """
        if position.quantity == 0:
            return Decimal("0")

        realized_pnl = (close_price - position.avg_entry_price) * abs(position.quantity)

        if position.side == "SHORT":
            realized_pnl = -realized_pnl

        position.realized_pnl += realized_pnl
        position.quantity = Decimal("0")
        position.side = "FLAT"
        position.updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Closed position {position.symbol} @ {close_price:.4f}, "
            f"realized_pnl={realized_pnl:.2f}, total={position.realized_pnl:.2f}"
        )

        await session.flush()
        return realized_pnl

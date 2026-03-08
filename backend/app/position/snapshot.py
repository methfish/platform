"""
Position snapshot service - captures point-in-time position state for history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import Position, PositionSnapshot
from app.position.pnl import compute_pnl_summary


async def take_snapshot(
    session: AsyncSession,
    positions: list[Position],
    mark_prices: dict[str, Decimal],
) -> list[PositionSnapshot]:
    """Create a snapshot of all positions with current mark prices."""
    now = datetime.now(timezone.utc)
    summary = compute_pnl_summary(positions)
    total_equity = summary.net_pnl  # Simplified; real equity includes balances

    snapshots = []
    for pos in positions:
        if pos.quantity <= 0:
            continue

        mark = mark_prices.get(pos.symbol, pos.avg_entry_price)
        snapshot = PositionSnapshot(
            position_id=pos.id,
            symbol=pos.symbol,
            exchange=pos.exchange,
            quantity=pos.quantity,
            mark_price=mark,
            unrealized_pnl=pos.unrealized_pnl,
            realized_pnl=pos.realized_pnl,
            total_equity=total_equity,
            snapshot_time=now,
        )
        session.add(snapshot)
        snapshots.append(snapshot)

    await session.flush()
    return snapshots

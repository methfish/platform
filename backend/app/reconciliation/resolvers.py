"""
Reconciliation break resolvers - strategies for resolving discrepancies.

In v1, most breaks require manual review. These resolvers provide
scaffolding for future auto-resolution logic.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BreakResolver:
    """Base resolver for reconciliation breaks."""

    async def resolve_position_mismatch(
        self,
        symbol: str,
        internal_qty: str,
        exchange_qty: str,
    ) -> str:
        """
        Resolve a position mismatch.

        In v1, log and flag for manual review.
        Future: auto-adjust internal state if exchange is source of truth.
        """
        logger.warning(
            f"Position mismatch for {symbol}: "
            f"internal={internal_qty}, exchange={exchange_qty}. "
            "Flagged for manual review."
        )
        return "MANUAL"

    async def resolve_missing_order(
        self,
        client_order_id: str,
        symbol: str,
    ) -> str:
        """
        Resolve an order that exists internally but not on exchange.

        Could mean: order was filled/cancelled and we missed the update,
        or order was never actually placed.
        """
        logger.warning(
            f"Missing order {client_order_id} for {symbol}. "
            "Order exists internally but not on exchange. "
            "Flagged for manual review."
        )
        return "MANUAL"

    async def resolve_unknown_order(
        self,
        client_order_id: str,
        symbol: str,
    ) -> str:
        """
        Resolve an order on exchange that doesn't exist internally.

        Could mean: order was placed outside the platform,
        or internal record was lost.
        """
        logger.warning(
            f"Unknown order {client_order_id} for {symbol}. "
            "Exists on exchange but not internally. "
            "Flagged for manual review."
        )
        return "MANUAL"

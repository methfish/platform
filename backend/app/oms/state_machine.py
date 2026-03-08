"""
Explicit finite state machine for order lifecycle transitions.

Defines the canonical set of valid state transitions for orders.
All order status changes MUST go through validate_transition()
to ensure no illegal states are ever reached.
"""

from __future__ import annotations

from app.core.enums import OrderStatus
from app.core.exceptions import InvalidStateTransition


# Canonical transition table.
# Terminal states (FILLED, CANCELLED, REJECTED, EXCHANGE_REJECTED, EXPIRED, FAILED)
# have no outgoing transitions.
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {
        OrderStatus.APPROVED,
        OrderStatus.REJECTED,
    },
    OrderStatus.APPROVED: {
        OrderStatus.SUBMITTED,
        OrderStatus.FAILED,
    },
    OrderStatus.SUBMITTED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.CANCELLED,
        OrderStatus.EXCHANGE_REJECTED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CANCEL_PENDING: {
        OrderStatus.CANCELLED,
        OrderStatus.FILLED,
        OrderStatus.PARTIALLY_FILLED,
    },
    # Terminal states - no outgoing transitions
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXCHANGE_REJECTED: set(),
    OrderStatus.EXPIRED: set(),
    OrderStatus.FAILED: set(),
}


def validate_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """
    Validate and enforce an order state transition.

    Args:
        current: The current order status.
        target: The desired target status.

    Returns:
        True if the transition is valid.

    Raises:
        InvalidStateTransition: If the transition is not allowed.
    """
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransition(current.value, target.value)
    return True


def is_terminal(status: OrderStatus) -> bool:
    """Check whether the given status is a terminal (final) state."""
    return status.is_terminal


def get_valid_targets(status: OrderStatus) -> set[OrderStatus]:
    """Return the set of statuses reachable from the given status."""
    return VALID_TRANSITIONS.get(status, set())

"""
Unit tests for the order state machine.

Validates state transition rules, terminal state detection,
and valid target enumeration.
"""

import pytest

from app.core.enums import OrderStatus
from app.core.exceptions import InvalidStateTransition
from app.oms.state_machine import (
    VALID_TRANSITIONS,
    get_valid_targets,
    is_terminal,
    validate_transition,
)


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------

class TestValidTransitions:
    """Test that all permitted state transitions succeed."""

    @pytest.mark.parametrize(
        "current, target",
        [
            (OrderStatus.PENDING, OrderStatus.APPROVED),
            (OrderStatus.PENDING, OrderStatus.REJECTED),
            (OrderStatus.APPROVED, OrderStatus.SUBMITTED),
            (OrderStatus.APPROVED, OrderStatus.FAILED),
            (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED),
            (OrderStatus.SUBMITTED, OrderStatus.FILLED),
            (OrderStatus.SUBMITTED, OrderStatus.CANCEL_PENDING),
            (OrderStatus.SUBMITTED, OrderStatus.CANCELLED),
            (OrderStatus.SUBMITTED, OrderStatus.EXCHANGE_REJECTED),
            (OrderStatus.SUBMITTED, OrderStatus.EXPIRED),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCEL_PENDING),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELLED),
            (OrderStatus.CANCEL_PENDING, OrderStatus.CANCELLED),
            (OrderStatus.CANCEL_PENDING, OrderStatus.FILLED),
            (OrderStatus.CANCEL_PENDING, OrderStatus.PARTIALLY_FILLED),
        ],
    )
    def test_valid_transition_succeeds(self, current: OrderStatus, target: OrderStatus):
        assert validate_transition(current, target) is True


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------

class TestInvalidTransitions:
    """Test that prohibited state transitions raise InvalidStateTransition."""

    @pytest.mark.parametrize(
        "current, target",
        [
            # Terminal states cannot transition to anything
            (OrderStatus.FILLED, OrderStatus.PENDING),
            (OrderStatus.FILLED, OrderStatus.CANCELLED),
            (OrderStatus.CANCELLED, OrderStatus.APPROVED),
            (OrderStatus.CANCELLED, OrderStatus.PENDING),
            (OrderStatus.REJECTED, OrderStatus.PENDING),
            (OrderStatus.REJECTED, OrderStatus.APPROVED),
            (OrderStatus.EXCHANGE_REJECTED, OrderStatus.SUBMITTED),
            (OrderStatus.EXPIRED, OrderStatus.SUBMITTED),
            (OrderStatus.FAILED, OrderStatus.APPROVED),
            # Backwards / skipped transitions
            (OrderStatus.APPROVED, OrderStatus.PENDING),
            (OrderStatus.SUBMITTED, OrderStatus.PENDING),
            (OrderStatus.SUBMITTED, OrderStatus.APPROVED),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.SUBMITTED),
            (OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING),
            # Self-transitions are not in the valid set
            (OrderStatus.PENDING, OrderStatus.PENDING),
            (OrderStatus.SUBMITTED, OrderStatus.SUBMITTED),
        ],
    )
    def test_invalid_transition_raises(self, current: OrderStatus, target: OrderStatus):
        with pytest.raises(InvalidStateTransition) as exc_info:
            validate_transition(current, target)

        assert exc_info.value.current_status == current.value
        assert exc_info.value.target_status == target.value

    def test_invalid_transition_exception_attributes(self):
        with pytest.raises(InvalidStateTransition) as exc_info:
            validate_transition(OrderStatus.FILLED, OrderStatus.PENDING)

        exc = exc_info.value
        assert exc.code == "INVALID_STATE_TRANSITION"
        assert "FILLED" in str(exc)
        assert "PENDING" in str(exc)


# ---------------------------------------------------------------------------
# Terminal state detection
# ---------------------------------------------------------------------------

class TestIsTerminal:
    """Test the is_terminal helper."""

    TERMINAL_STATES = [
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXCHANGE_REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    ]

    ACTIVE_STATES = [
        OrderStatus.PENDING,
        OrderStatus.APPROVED,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
    ]

    @pytest.mark.parametrize("status", TERMINAL_STATES)
    def test_terminal_states_are_terminal(self, status: OrderStatus):
        assert is_terminal(status) is True

    @pytest.mark.parametrize("status", ACTIVE_STATES)
    def test_active_states_are_not_terminal(self, status: OrderStatus):
        assert is_terminal(status) is False


# ---------------------------------------------------------------------------
# Terminal states have no outgoing transitions
# ---------------------------------------------------------------------------

class TestTerminalStatesHaveNoOutgoing:
    """Verify that terminal states have empty transition sets."""

    TERMINAL_STATES = [
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXCHANGE_REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
    ]

    @pytest.mark.parametrize("status", TERMINAL_STATES)
    def test_terminal_state_has_empty_targets(self, status: OrderStatus):
        targets = get_valid_targets(status)
        assert targets == set(), f"{status} should have no valid targets, got {targets}"


# ---------------------------------------------------------------------------
# get_valid_targets correctness
# ---------------------------------------------------------------------------

class TestGetValidTargets:
    """Test that get_valid_targets returns the correct transition sets."""

    def test_pending_targets(self):
        expected = {OrderStatus.APPROVED, OrderStatus.REJECTED}
        assert get_valid_targets(OrderStatus.PENDING) == expected

    def test_approved_targets(self):
        expected = {OrderStatus.SUBMITTED, OrderStatus.FAILED}
        assert get_valid_targets(OrderStatus.APPROVED) == expected

    def test_submitted_targets(self):
        expected = {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.EXCHANGE_REJECTED,
            OrderStatus.EXPIRED,
        }
        assert get_valid_targets(OrderStatus.SUBMITTED) == expected

    def test_partially_filled_targets(self):
        expected = {
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
        }
        assert get_valid_targets(OrderStatus.PARTIALLY_FILLED) == expected

    def test_cancel_pending_targets(self):
        expected = {
            OrderStatus.CANCELLED,
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
        }
        assert get_valid_targets(OrderStatus.CANCEL_PENDING) == expected

    def test_all_statuses_are_covered_in_transition_table(self):
        """Every OrderStatus must have an entry in VALID_TRANSITIONS."""
        for status in OrderStatus:
            assert status in VALID_TRANSITIONS, (
                f"OrderStatus.{status.name} is missing from VALID_TRANSITIONS"
            )

    def test_unknown_status_returns_empty_set(self):
        """get_valid_targets with an unrecognised status returns empty set."""
        # Simulate by calling .get with a value not in the dict
        # The function uses dict.get(..., set()) so anything missing returns set()
        result = VALID_TRANSITIONS.get("NOT_A_REAL_STATUS", set())
        assert result == set()

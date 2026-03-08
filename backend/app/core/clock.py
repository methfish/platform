"""
Abstracted clock for the Pensy platform.

Allows swapping real time for simulated time in tests and backtesting.
All services should use this clock instead of datetime.now() directly.
"""

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real system clock using UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class SimulatedClock:
    """Clock with manually controllable time for testing."""

    def __init__(self, start_time: datetime | None = None):
        self._time = start_time or datetime(2024, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._time

    def advance(self, **kwargs: float) -> None:
        from datetime import timedelta
        self._time += timedelta(**kwargs)

    def set_time(self, dt: datetime) -> None:
        self._time = dt

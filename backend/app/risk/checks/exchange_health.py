"""Exchange health risk check.

Validates that the exchange is responding and healthy.
Prevents trading if exchange API is down or slow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse

logger = logging.getLogger(__name__)


class ExchangeHealthCheck(BaseRiskCheck):
    """Check that the exchange is healthy and responsive."""

    def __init__(self, max_stale_seconds: int = 30):
        """
        Args:
            max_stale_seconds: Max time since last successful API call (default 30s).
        """
        self.max_stale_seconds = max_stale_seconds
        self._last_successful_ping: datetime | None = None
        self._exchange_healthy = True

    @property
    def name(self) -> str:
        return "exchange_health"

    def set_healthy(self, healthy: bool, timestamp: datetime | None = None) -> None:
        """Update exchange health status and timestamp."""
        self._exchange_healthy = healthy
        if healthy and timestamp:
            self._last_successful_ping = timestamp

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        # Check if exchange was recently pinged successfully
        if self._last_successful_ping is None:
            return self._skip(
                "Exchange health not yet initialized. "
                "Waiting for first successful API call."
            )

        now = datetime.now(timezone.utc)
        age = now - self._last_successful_ping
        max_age = timedelta(seconds=self.max_stale_seconds)

        # Check if data is stale
        if age > max_age:
            return self._fail(
                f"Exchange health data is stale ({age.total_seconds():.0f}s old). "
                f"Max allowed: {self.max_stale_seconds}s",
                age_seconds=age.total_seconds(),
                max_stale_seconds=self.max_stale_seconds,
            )

        # Check if exchange marked as unhealthy
        if not self._exchange_healthy:
            return self._fail(
                "Exchange is marked as unhealthy. Trading is blocked.",
                exchange_healthy=False,
            )

        return self._pass(
            "Exchange is healthy and responsive.",
            age_seconds=age.total_seconds(),
            max_stale_seconds=self.max_stale_seconds,
        )

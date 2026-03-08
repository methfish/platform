"""
Per-exchange rate limiter using token bucket algorithm.
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter for exchange API calls."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._tokens = max_requests
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            self._refill()
            while self._tokens <= 0:
                wait_time = self.window_seconds / self.max_requests
                await asyncio.sleep(wait_time)
                self._refill()
            self._tokens -= 1

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * (self.max_requests / self.window_seconds)
        self._tokens = min(self.max_requests, self._tokens + new_tokens)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens

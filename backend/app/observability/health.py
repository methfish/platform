"""
Health check logic for readiness and liveness probes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class HealthStatus:
    status: str = "healthy"
    version: str = "0.1.0"
    environment: str = "development"
    trading_mode: str = "PAPER"
    checks: dict[str, dict] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "version": self.version,
            "environment": self.environment,
            "trading_mode": self.trading_mode,
            "checks": self.checks,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
        }


async def check_database(session: AsyncSession) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis(redis_client) -> dict:
    try:
        if redis_client is None:
            return {"status": "not_configured"}
        await redis_client.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

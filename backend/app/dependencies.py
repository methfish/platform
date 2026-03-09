"""
FastAPI dependency injection.

Provides database sessions, services, and application state as dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_session
from app.exchange.base import ExchangeAdapter


@dataclass
class TradingState:
    """Runtime application state. Mutable, not persisted across restarts."""
    operator_confirmed_live: bool = False
    kill_switch_active: bool = False
    active_strategies: set[str] = field(default_factory=set)


# Global application state
_trading_state = TradingState()
_exchange_adapter: ExchangeAdapter | None = None


def get_trading_state() -> TradingState:
    return _trading_state


def set_exchange_adapter(adapter: ExchangeAdapter) -> None:
    global _exchange_adapter
    _exchange_adapter = adapter


def get_exchange_adapter() -> ExchangeAdapter:
    if _exchange_adapter is None:
        raise RuntimeError("Exchange adapter not initialized")
    return _exchange_adapter


_mm_arb_runner: Any = None


def set_mm_arb_runner(runner: Any) -> None:
    global _mm_arb_runner
    _mm_arb_runner = runner


def get_mm_arb_runner() -> Any:
    if _mm_arb_runner is None:
        raise RuntimeError("Strategy runner not initialized")
    return _mm_arb_runner


def is_live_trading_active(
    settings: Settings | None = None,
    state: TradingState | None = None,
) -> bool:
    """
    Check if live trading is fully enabled.

    Requires BOTH:
    1. LIVE_TRADING_ENABLED=true in environment config
    2. operator_confirmed_live=true set via admin API at runtime
    """
    s = settings or get_settings()
    t = state or get_trading_state()
    return s.LIVE_TRADING_ENABLED and t.operator_confirmed_live


async def get_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session

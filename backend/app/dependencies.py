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


_agent_registry: dict[str, Any] | None = None


def set_agent_registry(registry: dict[str, Any]) -> None:
    global _agent_registry
    _agent_registry = registry


def get_agent_registry() -> dict[str, Any]:
    if _agent_registry is None:
        raise RuntimeError("Agent registry not initialized")
    return _agent_registry


# --- OMS Service ---

_oms_service: Any = None


def set_oms_service(oms: Any) -> None:
    global _oms_service
    _oms_service = oms


def get_oms_service() -> Any:
    if _oms_service is None:
        raise RuntimeError("OMS service not initialized")
    return _oms_service


# --- Risk Engine ---

_risk_engine: Any = None


def set_risk_engine(engine: Any) -> None:
    global _risk_engine
    _risk_engine = engine


def get_risk_engine() -> Any:
    if _risk_engine is None:
        raise RuntimeError("Risk engine not initialized")
    return _risk_engine


# --- Position Tracker ---

_position_tracker: Any = None


def set_position_tracker(tracker: Any) -> None:
    global _position_tracker
    _position_tracker = tracker


def get_position_tracker() -> Any:
    if _position_tracker is None:
        raise RuntimeError("Position tracker not initialized")
    return _position_tracker


# --- Fill Handler ---

_fill_handler: Any = None


def set_fill_handler(handler: Any) -> None:
    global _fill_handler
    _fill_handler = handler


def get_fill_handler() -> Any:
    if _fill_handler is None:
        raise RuntimeError("Fill handler not initialized")
    return _fill_handler


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

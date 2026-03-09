"""
Event-driven trading simulator.

Public API:
    SimulatorEngine  — main replay engine
    SimulatorConfig  — configuration dataclass
    SimulatorResult  — output of a simulation run
    SimBar           — OHLCV bar input
    OrderSide, SimOrderType — enums for order submission
"""

from app.simulator.engine import SimulatorEngine, SimulatorResult
from app.simulator.types import (
    OrderSide,
    SimBar,
    SimOrderType,
    SimulatorConfig,
)

__all__ = [
    "SimulatorEngine",
    "SimulatorConfig",
    "SimulatorResult",
    "SimBar",
    "OrderSide",
    "SimOrderType",
]

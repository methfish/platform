"""
Abstract base class and data structures for risk checks.

Every risk check in the system inherits from BaseRiskCheck and
implements the evaluate() method. The context and response dataclasses
provide a consistent interface across all checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from app.core.enums import RiskCheckResult


@dataclass
class RiskCheckContext:
    """
    Context provided to each risk check for evaluation.

    Contains the order details, current market data, position state,
    and platform settings required for risk evaluation.
    """

    # Order details
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""  # BUY / SELL
    order_type: str = ""  # MARKET / LIMIT / etc.
    quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None
    strategy_id: Optional[str] = None
    exchange: str = ""

    # Market data
    last_price: Optional[Decimal] = None
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    mid_price: Optional[Decimal] = None

    # Position state
    current_position_quantity: Decimal = Decimal("0")
    current_position_notional: Decimal = Decimal("0")
    current_position_side: str = "FLAT"
    total_portfolio_notional: Decimal = Decimal("0")

    # Risk state accumulators
    daily_realized_pnl: Decimal = Decimal("0")
    daily_realized_pnl_by_strategy: dict[str, Decimal] = field(default_factory=dict)
    orders_in_last_minute: int = 0
    cancel_count: int = 0
    fill_count: int = 0
    peak_equity: Decimal = Decimal("0")
    current_equity: Decimal = Decimal("0")
    total_leverage: Decimal = Decimal("0")
    available_margin: Decimal = Decimal("0")

    # Recent orders for duplicate detection
    recent_orders: list[dict[str, Any]] = field(default_factory=list)

    # Trading hours / mode
    kill_switch_active: bool = False
    trading_mode: str = "PAPER"
    current_hour_utc: int = 0
    current_weekday: int = 0  # 0=Monday, 6=Sunday

    # Settings / limits (populated from config)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskCheckResponse:
    """
    Result of a single risk check evaluation.

    Attributes:
        result: PASS, FAIL, WARN, or SKIP.
        check_name: The canonical name of the risk check.
        message: Human-readable explanation.
        details: Arbitrary key-value details for diagnostics.
    """

    result: RiskCheckResult
    check_name: str
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class BaseRiskCheck(ABC):
    """
    Abstract base class for all risk checks.

    Subclasses must implement:
        - name (property): Canonical check name for logging/audit.
        - evaluate(ctx): Async method that returns a RiskCheckResponse.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Canonical name of this risk check (e.g. 'order_size')."""
        ...

    @abstractmethod
    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        """
        Evaluate the risk check against the provided context.

        Args:
            ctx: The risk check context containing order, market,
                 position, and settings data.

        Returns:
            A RiskCheckResponse indicating the check result.
        """
        ...

    def _pass(self, message: str = "", **details: Any) -> RiskCheckResponse:
        """Convenience: create a PASS response."""
        return RiskCheckResponse(
            result=RiskCheckResult.PASS,
            check_name=self.name,
            message=message,
            details=details,
        )

    def _fail(self, message: str, **details: Any) -> RiskCheckResponse:
        """Convenience: create a FAIL response."""
        return RiskCheckResponse(
            result=RiskCheckResult.FAIL,
            check_name=self.name,
            message=message,
            details=details,
        )

    def _warn(self, message: str, **details: Any) -> RiskCheckResponse:
        """Convenience: create a WARN response."""
        return RiskCheckResponse(
            result=RiskCheckResult.WARN,
            check_name=self.name,
            message=message,
            details=details,
        )

    def _skip(self, message: str = "", **details: Any) -> RiskCheckResponse:
        """Convenience: create a SKIP response."""
        return RiskCheckResponse(
            result=RiskCheckResult.SKIP,
            check_name=self.name,
            message=message,
            details=details,
        )

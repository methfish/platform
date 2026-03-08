"""
Risk engine - orchestrates pre-trade risk checks.

Runs all registered risk checks against an order and its context.
Supports short-circuit mode (stop on first FAIL) and run-all mode
(for diagnostics).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.enums import RiskCheckResult
from app.models.order import Order
from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse

logger = logging.getLogger(__name__)


@dataclass
class RiskEngineResult:
    """
    Aggregated result from the risk engine after running all checks.

    Attributes:
        passed: True if all checks passed (no FAIL results).
        results: List of individual check responses.
        failed_checks: Names of checks that returned FAIL.
        warned_checks: Names of checks that returned WARN.
    """

    passed: bool = True
    results: list[RiskCheckResponse] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    warned_checks: list[str] = field(default_factory=list)


class RiskEngine:
    """
    Pre-trade risk engine.

    Holds an ordered list of BaseRiskCheck instances and evaluates
    them against an order context. By default, short-circuits on the
    first FAIL for performance. Set run_all=True for full diagnostics.

    Args:
        checks: List of risk check instances to evaluate (in order).
    """

    def __init__(self, checks: Optional[list[BaseRiskCheck]] = None) -> None:
        self._checks: list[BaseRiskCheck] = checks or []

    @property
    def checks(self) -> list[BaseRiskCheck]:
        """Return the registered risk checks."""
        return list(self._checks)

    def register_check(self, check: BaseRiskCheck) -> None:
        """
        Register a new risk check.

        Args:
            check: A BaseRiskCheck instance to add.
        """
        self._checks.append(check)
        logger.info("Registered risk check: %s", check.name)

    def remove_check(self, name: str) -> None:
        """
        Remove a risk check by name.

        Args:
            name: The canonical name of the check to remove.
        """
        self._checks = [c for c in self._checks if c.name != name]

    async def evaluate_order(
        self,
        order: Order,
        context: Any = None,
        run_all: bool = False,
    ) -> RiskEngineResult:
        """
        Evaluate all risk checks against an order.

        Args:
            order: The Order model instance to evaluate.
            context: Optional pre-built RiskCheckContext. If None,
                     a basic context is built from the order fields.
            run_all: If True, runs all checks even after a FAIL.
                     If False (default), short-circuits on first FAIL.

        Returns:
            RiskEngineResult with aggregated pass/fail and per-check details.
        """
        if context is None:
            ctx = self._build_context_from_order(order)
        elif isinstance(context, RiskCheckContext):
            ctx = context
        else:
            ctx = self._build_context_from_order(order)

        result = RiskEngineResult()

        for check in self._checks:
            try:
                response = await check.evaluate(ctx)
            except Exception as exc:
                logger.exception(
                    "Risk check raised exception",
                    extra={"check": check.name, "error": str(exc)},
                )
                response = RiskCheckResponse(
                    result=RiskCheckResult.FAIL,
                    check_name=check.name,
                    message=f"Check raised exception: {exc}",
                    details={"exception": str(exc)},
                )

            result.results.append(response)

            if response.result == RiskCheckResult.FAIL:
                result.passed = False
                result.failed_checks.append(response.check_name)
                logger.warning(
                    "Risk check FAILED",
                    extra={
                        "check": response.check_name,
                        "message": response.message,
                        "order_id": ctx.order_id,
                    },
                )
                if not run_all:
                    break

            elif response.result == RiskCheckResult.WARN:
                result.warned_checks.append(response.check_name)
                logger.info(
                    "Risk check WARN",
                    extra={
                        "check": response.check_name,
                        "message": response.message,
                        "order_id": ctx.order_id,
                    },
                )

        return result

    def _build_context_from_order(self, order: Order) -> RiskCheckContext:
        """
        Build a minimal RiskCheckContext from an Order model.

        This provides a baseline context. Callers should provide a
        fully populated context for production use.

        Args:
            order: The Order to build context from.

        Returns:
            A RiskCheckContext with order fields populated.
        """
        return RiskCheckContext(
            order_id=str(order.id),
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            strategy_id=str(order.strategy_id) if order.strategy_id else None,
            exchange=order.exchange,
            trading_mode=order.trading_mode,
        )

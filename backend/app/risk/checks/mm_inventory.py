"""
Market-making inventory limit risk check.

Prevents a market-making strategy from exceeding its configured
max_inventory by rejecting orders that would increase exposure
beyond the limit.
"""

from __future__ import annotations

from decimal import Decimal

from app.dependencies import get_mm_arb_runner
from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse
from app.strategy.market_making import MarketMakingStrategy


class MMInventoryCheck(BaseRiskCheck):
    """Check that a MM strategy order will not exceed max inventory."""

    @property
    def name(self) -> str:
        return "mm_inventory"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        # Only applies to orders from a strategy
        if not ctx.strategy_id:
            return self._skip("No strategy_id on order.")

        try:
            runner = get_mm_arb_runner()
        except RuntimeError:
            return self._skip("Strategy runner not initialized.")

        # Find the strategy instance
        strategy = None
        for sname, s in runner._strategies.items():
            db_id = runner._strategy_db_ids.get(sname)
            if db_id and str(db_id) == ctx.strategy_id:
                strategy = s
                break

        if strategy is None:
            return self._skip("Strategy not found in runner.")

        if not isinstance(strategy, MarketMakingStrategy):
            return self._skip("Not a market-making strategy.")

        max_inventory = strategy._config.max_inventory
        current_inventory = strategy._current_inventory

        # Project resulting inventory
        if ctx.side == "BUY":
            projected = current_inventory + ctx.quantity
        else:
            projected = current_inventory - ctx.quantity

        if abs(projected) > max_inventory:
            return self._fail(
                f"MM inventory would reach {projected} "
                f"(max {max_inventory}).",
                current_inventory=str(current_inventory),
                projected_inventory=str(projected),
                max_inventory=str(max_inventory),
            )

        return self._pass(
            "MM inventory within limits.",
            current_inventory=str(current_inventory),
            projected_inventory=str(projected),
            max_inventory=str(max_inventory),
        )

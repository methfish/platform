"""
Entry Planning skill.

For each allocation, decides the order entry style based on the
current bid/ask spread:

  - spread < 0.1%:  market order
  - spread < 0.5%:  limit at mid price
  - spread >= 0.5%: staged entry (multiple limit orders)

Deterministic - pure computation on upstream allocations and
market context data.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)

# Spread thresholds for entry style decision.
_MARKET_ORDER_THRESHOLD = Decimal("0.001")   # 0.1%
_LIMIT_ORDER_THRESHOLD = Decimal("0.005")    # 0.5%

# Staged entry: split into this many tranches.
_STAGED_TRANCHES = 3


class EntryPlanningSkill(BaseSkill):
    """Decide order type and pricing for each allocated position."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "entry_planning"

    @property
    def name(self) -> str:
        return "Entry Planning"

    @property
    def description(self) -> str:
        return (
            "Determines entry style (market, limit, staged) for each "
            "allocation based on current bid/ask spread."
        )

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Execution config
    # ------------------------------------------------------------------

    @property
    def execution_type(self) -> SkillExecutionType:
        return SkillExecutionType.DETERMINISTIC

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    @property
    def prerequisites(self) -> list[str]:
        return ["position_sizing"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        sizing_output = ctx.upstream_results["position_sizing"].output
        allocations: dict = sizing_output.get("allocations", {})

        if not allocations:
            return self._success(
                output={"order_plans": []},
                message="No allocations to plan entries for.",
            )

        # We also need market context for spread data.
        market_output = ctx.upstream_results.get("market_context")
        symbol_contexts_list: list[dict] = (
            market_output.output.get("symbol_contexts", [])
            if market_output
            else []
        )
        symbol_ctx_map = {sc["symbol"]: sc for sc in symbol_contexts_list}

        order_plans: list[dict] = []

        for symbol, alloc in allocations.items():
            quantity = Decimal(alloc["quantity"])
            if quantity <= 0:
                continue

            sc = symbol_ctx_map.get(symbol, {})
            spread_pct = Decimal(sc.get("spread_pct", "0"))
            mid_price = Decimal(sc.get("mid_price", "0"))
            bid = Decimal(sc.get("bid_price", "0"))
            ask = Decimal(sc.get("ask_price", "0"))

            if spread_pct < _MARKET_ORDER_THRESHOLD:
                # Tight spread - use market order.
                order_plans.append({
                    "symbol": symbol,
                    "side": "BUY",
                    "order_type": "MARKET",
                    "price": None,
                    "quantity": str(quantity),
                    "rationale": (
                        f"Spread {spread_pct * 100:.4f}% < 0.1% threshold. "
                        f"Market order appropriate."
                    ),
                })

            elif spread_pct < _LIMIT_ORDER_THRESHOLD:
                # Moderate spread - limit at mid price.
                limit_price = mid_price.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP,
                )
                order_plans.append({
                    "symbol": symbol,
                    "side": "BUY",
                    "order_type": "LIMIT",
                    "price": str(limit_price),
                    "quantity": str(quantity),
                    "rationale": (
                        f"Spread {spread_pct * 100:.4f}% is moderate. "
                        f"Limit at mid price {limit_price}."
                    ),
                })

            else:
                # Wide spread - staged entry with multiple limit orders.
                plans = self._staged_entry(
                    symbol, quantity, bid, ask, mid_price, spread_pct,
                )
                order_plans.extend(plans)

        return self._success(
            output={
                "order_plans": order_plans,
                "num_orders": len(order_plans),
            },
            message=f"Planned {len(order_plans)} orders for {len(allocations)} symbols.",
        )

    # ------------------------------------------------------------------
    # Staged entry helper
    # ------------------------------------------------------------------

    @staticmethod
    def _staged_entry(
        symbol: str,
        total_quantity: Decimal,
        bid: Decimal,
        ask: Decimal,
        mid: Decimal,
        spread_pct: Decimal,
    ) -> list[dict]:
        """
        Split into multiple limit orders at different price levels
        between the bid and mid.
        """
        plans: list[dict] = []
        tranche_qty = (total_quantity / Decimal(str(_STAGED_TRANCHES))).quantize(
            Decimal("0.00000001"),
        )

        if bid <= 0 or mid <= 0:
            # Fallback: single limit at mid.
            return [{
                "symbol": symbol,
                "side": "BUY",
                "order_type": "LIMIT",
                "price": str(mid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "quantity": str(total_quantity),
                "rationale": (
                    f"Wide spread ({spread_pct * 100:.4f}%) but insufficient "
                    f"price data for staging. Single limit at mid."
                ),
            }]

        step = (mid - bid) / Decimal(str(_STAGED_TRANCHES))

        for i in range(_STAGED_TRANCHES):
            price = (bid + step * Decimal(str(i + 1))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            # Last tranche absorbs remainder.
            qty = (
                tranche_qty
                if i < _STAGED_TRANCHES - 1
                else total_quantity - tranche_qty * Decimal(str(_STAGED_TRANCHES - 1))
            )
            plans.append({
                "symbol": symbol,
                "side": "BUY",
                "order_type": "LIMIT",
                "price": str(price),
                "quantity": str(qty),
                "rationale": (
                    f"Staged entry {i + 1}/{_STAGED_TRANCHES} at {price}. "
                    f"Wide spread ({spread_pct * 100:.4f}%)."
                ),
            })

        return plans

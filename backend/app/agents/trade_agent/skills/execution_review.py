"""
Execution Review skill.

Compares the intended order plan (from trade_decision) against
actual execution outcomes if they are available in the context.
If no execution data is present yet, produces a "pending_review"
placeholder.

Deterministic - pure comparison of planned vs actual fills.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
    SkillStatus,
)


class ExecutionReviewSkill(BaseSkill):
    """Compare intended orders against actual execution outcomes."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "execution_review"

    @property
    def name(self) -> str:
        return "Execution Review"

    @property
    def description(self) -> str:
        return (
            "Compares intended order plan vs actual execution outcomes. "
            "Reports slippage, fill quality, and deviations."
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
        return ["trade_decision"]

    @property
    def required_inputs(self) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        decision_result = ctx.upstream_results.get("trade_decision")

        # If decision was NO_TRADE, nothing to review.
        if decision_result:
            decision = decision_result.output.get("decision", "")
            if decision == "NO_TRADE":
                return self._skip("Decision was NO_TRADE - nothing to review.")

        # Check for execution data in context.
        # Execution outcomes may be stored in settings or a dedicated
        # field, depending on how the execution layer reports back.
        execution_data: list[dict] = ctx.settings.get("execution_outcomes", [])

        if not execution_data:
            return self._success(
                output={
                    "status": "pending_review",
                    "slippage_summary": {},
                    "fill_quality": "pending",
                    "deviation_notes": [
                        "No execution data available yet. "
                        "Review will be completed after order fills.",
                    ],
                },
                message="Execution review pending - no fill data available.",
            )

        # --- Compare planned vs actual ---
        selected_orders: list[dict] = (
            decision_result.output.get("selected_orders", [])
            if decision_result
            else []
        )

        # Build lookup: symbol -> planned orders.
        planned_by_symbol: dict[str, list[dict]] = {}
        for order in selected_orders:
            sym = order.get("symbol", "")
            planned_by_symbol.setdefault(sym, []).append(order)

        slippage_entries: list[dict] = []
        deviation_notes: list[str] = []
        total_planned_notional = Decimal("0")
        total_actual_notional = Decimal("0")

        for fill in execution_data:
            symbol = fill.get("symbol", "")
            fill_price = Decimal(str(fill.get("fill_price", "0")))
            fill_qty = Decimal(str(fill.get("fill_quantity", "0")))
            actual_notional = fill_price * fill_qty

            # Find matching planned order.
            planned_list = planned_by_symbol.get(symbol, [])
            if not planned_list:
                deviation_notes.append(
                    f"Unexpected fill for {symbol} - no matching plan."
                )
                continue

            planned = planned_list[0]
            planned_price = (
                Decimal(planned["price"])
                if planned.get("price")
                else fill_price
            )
            planned_qty = Decimal(planned.get("quantity", "0"))
            planned_notional = planned_price * planned_qty

            # Slippage: (fill_price - planned_price) / planned_price
            if planned_price > 0:
                slippage_pct = (
                    (fill_price - planned_price) / planned_price
                )
            else:
                slippage_pct = Decimal("0")

            slippage_entries.append({
                "symbol": symbol,
                "planned_price": str(planned_price),
                "fill_price": str(fill_price),
                "slippage_pct": str(slippage_pct),
                "planned_quantity": str(planned_qty),
                "fill_quantity": str(fill_qty),
            })

            total_planned_notional += planned_notional
            total_actual_notional += actual_notional

            # Quantity deviation.
            if fill_qty != planned_qty:
                deviation_notes.append(
                    f"{symbol}: quantity deviation "
                    f"planned={planned_qty} filled={fill_qty}"
                )

        # Aggregate fill quality.
        if total_planned_notional > 0:
            overall_slippage = (
                (total_actual_notional - total_planned_notional)
                / total_planned_notional
            )
            if abs(overall_slippage) < Decimal("0.001"):
                fill_quality = "excellent"
            elif abs(overall_slippage) < Decimal("0.005"):
                fill_quality = "good"
            elif abs(overall_slippage) < Decimal("0.01"):
                fill_quality = "acceptable"
            else:
                fill_quality = "poor"
        else:
            overall_slippage = Decimal("0")
            fill_quality = "unknown"

        slippage_summary = {
            "overall_slippage_pct": str(overall_slippage),
            "total_planned_notional": str(total_planned_notional),
            "total_actual_notional": str(total_actual_notional),
            "entries": slippage_entries,
        }

        return self._success(
            output={
                "status": "reviewed",
                "slippage_summary": slippage_summary,
                "fill_quality": fill_quality,
                "deviation_notes": deviation_notes,
            },
            message=(
                f"Execution review complete. Fill quality: {fill_quality}. "
                f"Overall slippage: {overall_slippage * 100:.4f}%."
            ),
        )

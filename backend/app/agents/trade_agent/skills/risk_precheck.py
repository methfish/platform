"""
Risk Pre-check skill (SAFETY GATE).

Validates each planned order against risk rules before execution.
If any order violates a rule, that order is denied. If all orders
are denied the skill returns FAILURE to short-circuit the pipeline.

Deterministic, risk_level=CRITICAL - this is the last line of
defence before orders are submitted.

Checks performed per order:
  1. Order notional vs max_order_notional from settings.
  2. Position limit will not be exceeded.
  3. Kill switch is not active.
  4. Symbol is whitelisted.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.skill_base import BaseSkill
from app.agents.types import (
    SkillContext,
    SkillExecutionType,
    SkillResult,
    SkillRiskLevel,
)


class RiskPrecheckSkill(BaseSkill):
    """Safety gate: validate planned orders against risk rules."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def skill_id(self) -> str:
        return "risk_precheck"

    @property
    def name(self) -> str:
        return "Risk Pre-check"

    @property
    def description(self) -> str:
        return (
            "Safety gate that validates each planned order against risk "
            "rules: max notional, position limits, kill switch, and "
            "symbol whitelist."
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
        return SkillRiskLevel.CRITICAL

    @property
    def prerequisites(self) -> list[str]:
        return ["entry_planning"]

    @property
    def required_inputs(self) -> list[str]:
        return ["symbols"]

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    async def execute(self, ctx: SkillContext) -> SkillResult:
        entry_output = ctx.upstream_results["entry_planning"].output
        order_plans: list[dict] = entry_output.get("order_plans", [])

        if not order_plans:
            return self._success(
                output={
                    "checked_orders": [],
                    "triggered_rules": [],
                },
                message="No orders to check.",
            )

        # Risk parameters from settings and risk_state.
        max_order_notional = Decimal(
            str(ctx.settings.get("MAX_ORDER_NOTIONAL", "10000"))
        )
        max_position_notional = Decimal(
            str(ctx.settings.get("MAX_POSITION_NOTIONAL", "50000"))
        )
        kill_switch_active = ctx.risk_state.get("kill_switch_active", False)
        symbol_whitelist: list[str] | None = ctx.settings.get("SYMBOL_WHITELIST")

        checked_orders: list[dict] = []
        triggered_rules: list[dict] = []
        any_allowed = False

        for order in order_plans:
            symbol = order["symbol"]
            quantity = Decimal(order.get("quantity", "0"))
            price = Decimal(order["price"]) if order.get("price") else None
            violations: list[str] = []

            # --- Check 1: Kill switch ---
            if kill_switch_active:
                violations.append("kill_switch_active")

            # --- Check 2: Symbol whitelist ---
            if symbol_whitelist is not None and symbol not in symbol_whitelist:
                violations.append(f"symbol_not_whitelisted:{symbol}")

            # --- Check 3: Order notional ---
            if price and price > 0:
                notional = quantity * price
            else:
                # Estimate using market data.
                md = ctx.market_data.get(symbol, {})
                est_price = Decimal(str(md.get("last_price", "0")))
                notional = quantity * est_price if est_price > 0 else Decimal("0")

            if notional > max_order_notional:
                violations.append(
                    f"order_notional_exceeded:{notional}>{max_order_notional}"
                )

            # --- Check 4: Position limit ---
            current_pos = ctx.current_positions.get(symbol, {})
            current_notional = Decimal(
                str(current_pos.get("notional", "0"))
            )
            projected_notional = current_notional + notional
            if projected_notional > max_position_notional:
                violations.append(
                    f"position_limit_exceeded:{projected_notional}>{max_position_notional}"
                )

            # Build checked order.
            allowed = len(violations) == 0
            if allowed:
                any_allowed = True

            checked_order = {
                **order,
                "allowed": allowed,
                "violations": violations,
                "estimated_notional": str(notional),
            }
            checked_orders.append(checked_order)

            if violations:
                triggered_rules.append({
                    "symbol": symbol,
                    "violations": violations,
                })

        # If every order was denied, FAIL (CRITICAL) to short-circuit.
        if not any_allowed:
            return self._failure(
                message=(
                    f"All {len(order_plans)} orders denied by risk rules. "
                    f"Triggered: {triggered_rules}"
                ),
                checked_orders=checked_orders,
                triggered_rules=triggered_rules,
            )

        return self._success(
            output={
                "checked_orders": checked_orders,
                "triggered_rules": triggered_rules,
                "allowed_count": sum(1 for co in checked_orders if co["allowed"]),
                "denied_count": sum(1 for co in checked_orders if not co["allowed"]),
            },
            message=(
                f"Risk precheck complete: "
                f"{sum(1 for co in checked_orders if co['allowed'])} allowed, "
                f"{sum(1 for co in checked_orders if not co['allowed'])} denied."
            ),
        )

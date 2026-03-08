"""
Kill switch risk check.

Checks whether the global kill switch is active. When active,
ALL orders are rejected unconditionally. This is the highest
priority safety check and should be evaluated first.
"""

from __future__ import annotations

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class KillSwitchCheck(BaseRiskCheck):
    """Check if the global kill switch is active (blocks all orders)."""

    @property
    def name(self) -> str:
        return "kill_switch"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        if ctx.kill_switch_active:
            return self._fail(
                "Kill switch is active. All orders are blocked.",
                kill_switch_active=True,
            )

        return self._pass(
            "Kill switch is not active.",
            kill_switch_active=False,
        )

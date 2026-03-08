"""Symbol whitelist risk check.

Validates that the order symbol is in the configured whitelist.
Prevents accidental trading of unauthorized symbols.
"""

from __future__ import annotations

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class SymbolWhitelistCheck(BaseRiskCheck):
    """Check that the symbol is in the approved whitelist."""

    @property
    def name(self) -> str:
        return "symbol_whitelist"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        # Get whitelist from context settings
        whitelist = ctx.settings.get("SYMBOL_WHITELIST_SET", set())

        # If whitelist is empty, all symbols are allowed
        if not whitelist:
            return self._skip(
                "Symbol whitelist is empty. All symbols are allowed."
            )

        # Check if symbol is in whitelist
        symbol = ctx.symbol.upper() if ctx.symbol else ""
        if symbol not in whitelist:
            return self._fail(
                f"Symbol {symbol} is not in the approved whitelist. "
                f"Approved symbols: {sorted(whitelist)}",
                symbol=symbol,
                whitelist=sorted(whitelist),
            )

        return self._pass(
            f"Symbol {symbol} is approved.",
            symbol=symbol,
        )

"""
Symbol whitelist risk check.

Validates that the order symbol is in the allowed whitelist.
If the whitelist is empty, all symbols are allowed (pass by default).
"""

from __future__ import annotations

from app.risk.checks.base import BaseRiskCheck, RiskCheckContext, RiskCheckResponse


class SymbolWhitelistCheck(BaseRiskCheck):
    """Check that the symbol is in the configured whitelist (if one exists)."""

    @property
    def name(self) -> str:
        return "symbol_whitelist"

    async def evaluate(self, ctx: RiskCheckContext) -> RiskCheckResponse:
        whitelist_raw = ctx.settings.get("SYMBOL_WHITELIST", "")

        # Build whitelist set
        if isinstance(whitelist_raw, set):
            whitelist = whitelist_raw
        elif isinstance(whitelist_raw, (list, tuple)):
            whitelist = set(whitelist_raw)
        elif isinstance(whitelist_raw, str):
            if not whitelist_raw.strip():
                whitelist = set()
            else:
                whitelist = {
                    s.strip().upper()
                    for s in whitelist_raw.split(",")
                    if s.strip()
                }
        else:
            whitelist = set()

        # Empty whitelist means all symbols are allowed
        if not whitelist:
            return self._pass("No symbol whitelist configured; all symbols allowed.")

        symbol = ctx.symbol.upper().strip()
        if symbol not in whitelist:
            return self._fail(
                f"Symbol {symbol} is not in the allowed whitelist.",
                symbol=symbol,
                whitelist=sorted(whitelist),
            )

        return self._pass(
            f"Symbol {symbol} is whitelisted.",
            symbol=symbol,
        )

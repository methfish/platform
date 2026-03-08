"""
Reconciliation comparators - utility functions for comparing values.
"""

from __future__ import annotations

from decimal import Decimal


def quantities_match(
    internal: Decimal,
    external: Decimal,
    tolerance: Decimal = Decimal("0.00001"),
) -> bool:
    """Check if two quantities are equal within tolerance."""
    return abs(internal - external) <= tolerance


def prices_match(
    internal: Decimal,
    external: Decimal,
    tolerance_pct: Decimal = Decimal("0.001"),
) -> bool:
    """Check if two prices are equal within percentage tolerance."""
    if external == 0:
        return internal == 0
    deviation = abs(internal - external) / external
    return deviation <= tolerance_pct

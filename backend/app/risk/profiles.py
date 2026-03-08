"""
Risk profiles - predefined sets of risk limit overrides.

Profiles allow switching between different risk postures
(conservative, moderate, aggressive) without editing individual
settings. Each profile is a dict of setting keys to override values.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


# Conservative profile: tight limits for low-risk / onboarding.
CONSERVATIVE: dict[str, Any] = {
    "MAX_ORDER_NOTIONAL": Decimal("2000.0"),
    "MAX_ORDER_QUANTITY": Decimal("10.0"),
    "MAX_POSITION_NOTIONAL": Decimal("10000.0"),
    "MAX_GROSS_EXPOSURE": Decimal("20000.0"),
    "MAX_DAILY_LOSS": Decimal("1000.0"),
    "MAX_OPEN_ORDERS": 5,
    "PRICE_DEVIATION_THRESHOLD": Decimal("0.02"),
    "MAX_ORDERS_PER_MINUTE": 10,
    "MAX_DRAWDOWN_PCT": Decimal("0.03"),
    "MAX_LEVERAGE": Decimal("1.0"),
    "MAX_CONCENTRATION_PCT": Decimal("0.25"),
    "MAX_CANCEL_TO_FILL_RATIO": Decimal("5.0"),
}

# Moderate profile: balanced limits for standard operation.
MODERATE: dict[str, Any] = {
    "MAX_ORDER_NOTIONAL": Decimal("10000.0"),
    "MAX_ORDER_QUANTITY": Decimal("100.0"),
    "MAX_POSITION_NOTIONAL": Decimal("50000.0"),
    "MAX_GROSS_EXPOSURE": Decimal("100000.0"),
    "MAX_DAILY_LOSS": Decimal("5000.0"),
    "MAX_OPEN_ORDERS": 20,
    "PRICE_DEVIATION_THRESHOLD": Decimal("0.05"),
    "MAX_ORDERS_PER_MINUTE": 30,
    "MAX_DRAWDOWN_PCT": Decimal("0.05"),
    "MAX_LEVERAGE": Decimal("3.0"),
    "MAX_CONCENTRATION_PCT": Decimal("0.40"),
    "MAX_CANCEL_TO_FILL_RATIO": Decimal("10.0"),
}

# Aggressive profile: wider limits for experienced operators / HFT.
AGGRESSIVE: dict[str, Any] = {
    "MAX_ORDER_NOTIONAL": Decimal("50000.0"),
    "MAX_ORDER_QUANTITY": Decimal("1000.0"),
    "MAX_POSITION_NOTIONAL": Decimal("200000.0"),
    "MAX_GROSS_EXPOSURE": Decimal("500000.0"),
    "MAX_DAILY_LOSS": Decimal("20000.0"),
    "MAX_OPEN_ORDERS": 50,
    "PRICE_DEVIATION_THRESHOLD": Decimal("0.10"),
    "MAX_ORDERS_PER_MINUTE": 60,
    "MAX_DRAWDOWN_PCT": Decimal("0.10"),
    "MAX_LEVERAGE": Decimal("10.0"),
    "MAX_CONCENTRATION_PCT": Decimal("0.60"),
    "MAX_CANCEL_TO_FILL_RATIO": Decimal("20.0"),
}


# Profile registry keyed by name
RISK_PROFILES: dict[str, dict[str, Any]] = {
    "conservative": CONSERVATIVE,
    "moderate": MODERATE,
    "aggressive": AGGRESSIVE,
}


def get_profile(name: str) -> dict[str, Any]:
    """
    Retrieve a risk profile by name.

    Args:
        name: Profile name (conservative, moderate, aggressive).

    Returns:
        A dict of setting keys to their override values.

    Raises:
        KeyError: If the profile name is not recognized.
    """
    key = name.lower().strip()
    if key not in RISK_PROFILES:
        available = ", ".join(sorted(RISK_PROFILES.keys()))
        raise KeyError(
            f"Unknown risk profile '{name}'. Available profiles: {available}"
        )
    return dict(RISK_PROFILES[key])


def apply_profile(settings_dict: dict[str, Any], profile_name: str) -> dict[str, Any]:
    """
    Apply a risk profile's overrides on top of existing settings.

    Args:
        settings_dict: Current settings as a dict.
        profile_name: Name of the profile to apply.

    Returns:
        A new dict with the profile overrides merged in.
    """
    profile = get_profile(profile_name)
    merged = dict(settings_dict)
    merged.update(profile)
    return merged

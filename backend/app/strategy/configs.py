"""
Strategy configuration schemas.

Pydantic models that validate the config_json JSONB field
for each strategy type.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class MarketMakingConfigSchema(BaseModel):
    """Validates market-making strategy config_json."""

    symbol: str
    spread_bps: Decimal = Field(ge=1, le=1000, default=Decimal("10"))
    order_quantity: Decimal = Field(gt=0, default=Decimal("0.01"))
    num_levels: int = Field(ge=1, le=10, default=1)
    level_spacing_bps: Decimal = Field(ge=1, default=Decimal("5"))
    max_inventory: Decimal = Field(gt=0, default=Decimal("0.5"))
    inventory_skew_factor: Decimal = Field(ge=0, le=1, default=Decimal("0.5"))
    requote_threshold_bps: Decimal = Field(ge=1, default=Decimal("5"))
    min_requote_interval_ms: int = Field(ge=100, default=500)


class ArbitrageConfigSchema(BaseModel):
    """Validates arbitrage strategy config_json."""

    symbol: str
    exchange_a: str
    exchange_b: str
    min_spread_bps: Decimal = Field(ge=1, default=Decimal("5"))
    order_quantity: Decimal = Field(gt=0, default=Decimal("0.01"))
    max_open_arbs: int = Field(ge=1, le=10, default=3)
    max_leg_risk_seconds: float = Field(ge=1, le=30, default=5.0)
    use_market_orders: bool = True
    max_inventory_imbalance: Decimal = Field(ge=0, default=Decimal("0.1"))


STRATEGY_CONFIG_MAP: dict[str, type[BaseModel]] = {
    "MARKET_MAKING": MarketMakingConfigSchema,
    "ARBITRAGE": ArbitrageConfigSchema,
}


def validate_strategy_config(strategy_type: str, config: dict[str, Any]) -> BaseModel:
    """Validate and return parsed config for a strategy type."""
    schema_cls = STRATEGY_CONFIG_MAP.get(strategy_type)
    if schema_cls is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    return schema_cls(**config)

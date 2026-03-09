"""
Request/response schemas for the strategy engine API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CreateStrategyRequest(BaseModel):
    name: str = Field(max_length=64)
    description: str | None = None
    strategy_type: str = Field(pattern="^(MARKET_MAKING|ARBITRAGE)$")
    trading_mode: str = Field(default="PAPER", pattern="^(PAPER|LIVE)$")
    config_json: dict[str, Any]


class UpdateStrategyConfigRequest(BaseModel):
    config_json: dict[str, Any]


class StrategyResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    strategy_type: str
    status: str
    trading_mode: str
    config_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyPnLResponse(BaseModel):
    strategy_name: str = ""
    realized_pnl: str = "0"
    unrealized_pnl: str = "0"
    net_pnl: str = "0"
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_volume: str = "0"
    total_commission: str = "0"
    pnl_per_trade: str = "0"
    start_time: datetime | None = None


class StrategyRuntimeStatus(BaseModel):
    name: str
    status: str
    strategy_type: str = ""
    uptime_seconds: float | None = None
    ticks_processed: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    active_orders: int = 0
    current_inventory: dict[str, str] = {}
    pnl: StrategyPnLResponse | None = None

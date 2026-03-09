"""
Agent skill system types - enums, context, and result dataclasses.

Mirrors the risk module's RiskCheckContext/RiskCheckResponse pattern.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class SkillExecutionType(str, Enum):
    """How a skill computes its output."""
    DETERMINISTIC = "DETERMINISTIC"
    MODEL_ASSISTED = "MODEL_ASSISTED"
    HYBRID = "HYBRID"


class SkillStatus(str, Enum):
    """Result status of a skill invocation."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class SkillRiskLevel(str, Enum):
    """How dangerous this skill's output is if wrong."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AgentType(str, Enum):
    """Agent categories."""
    TRADE_DECISION = "TRADE_DECISION"
    FAILURE_ANALYSIS = "FAILURE_ANALYSIS"
    RESEARCH = "RESEARCH"
    STRATEGY_CODING = "STRATEGY_CODING"


@dataclass
class SkillContext:
    """
    Read-only context provided to every skill invocation.

    Mirrors RiskCheckContext - a flat dataclass with all
    data a skill might need. Skills pick what they need.
    """

    # Identity
    agent_type: AgentType = AgentType.TRADE_DECISION
    invocation_id: Optional[UUID] = None
    correlation_id: str = ""

    # Market data snapshot
    symbol: str = ""
    symbols: list[str] = field(default_factory=list)
    last_price: Optional[Decimal] = None
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    market_data: dict[str, Any] = field(default_factory=dict)

    # Position / portfolio state
    current_positions: dict[str, Any] = field(default_factory=dict)
    total_portfolio_value: Decimal = Decimal("0")
    available_capital: Decimal = Decimal("0")

    # Budget / allocation
    budget: dict[str, Any] = field(default_factory=dict)

    # Risk state
    risk_state: dict[str, Any] = field(default_factory=dict)

    # Previous skill outputs (skill_id -> SkillResult)
    upstream_results: dict[str, SkillResult] = field(default_factory=dict)

    # Failure / incident data (for Agent B)
    incident_data: dict[str, Any] = field(default_factory=dict)
    order_history: list[dict[str, Any]] = field(default_factory=list)
    trade_history: list[dict[str, Any]] = field(default_factory=list)

    # Settings / config
    settings: dict[str, Any] = field(default_factory=dict)

    # Research context (for Research Agent)
    backtest_results: list[dict[str, Any]] = field(default_factory=list)
    sweep_results: list[dict[str, Any]] = field(default_factory=list)
    collected_data_summary: dict[str, Any] = field(default_factory=dict)

    # Strategy coding context (for Strategy Coding Agent)
    strategy_code: str = ""
    code_modification_request: str = ""
    generated_strategy_name: str = ""

    trading_mode: str = "PAPER"

    # Timing
    timestamp: float = field(default_factory=time.time)


@dataclass
class SkillResult:
    """
    Result of a single skill execution.

    Mirrors RiskCheckResponse with added timing, version, and
    confidence fields.
    """

    skill_id: str
    status: SkillStatus
    output: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    execution_time_ms: float = 0.0
    version: str = "1.0.0"
    requires_human_review: bool = False
    error: Optional[str] = None

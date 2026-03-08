"""
Prometheus metrics for the Pensy platform.
"""

from prometheus_client import Counter, Histogram, Gauge

# Order metrics
orders_submitted = Counter(
    "pensy_orders_submitted_total",
    "Total orders submitted",
    ["exchange", "symbol", "side", "trading_mode"],
)
orders_filled = Counter(
    "pensy_orders_filled_total",
    "Total orders filled",
    ["exchange", "symbol", "side", "trading_mode"],
)
orders_rejected = Counter(
    "pensy_orders_rejected_total",
    "Total orders rejected",
    ["exchange", "reason"],
)

# Risk metrics
risk_checks_run = Counter(
    "pensy_risk_checks_total",
    "Total risk checks executed",
    ["check_name", "result"],
)
kill_switch_active = Gauge(
    "pensy_kill_switch_active",
    "Whether the kill switch is currently active",
)

# Exchange metrics
exchange_request_duration = Histogram(
    "pensy_exchange_request_duration_seconds",
    "Duration of exchange API requests",
    ["exchange", "operation"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
exchange_errors = Counter(
    "pensy_exchange_errors_total",
    "Exchange API errors",
    ["exchange", "error_type"],
)

# Position metrics
open_positions = Gauge(
    "pensy_open_positions",
    "Number of open positions",
    ["exchange", "trading_mode"],
)
total_unrealized_pnl = Gauge(
    "pensy_total_unrealized_pnl",
    "Total unrealized PnL",
    ["trading_mode"],
)

# Market data metrics
market_data_updates = Counter(
    "pensy_market_data_updates_total",
    "Market data updates received",
    ["exchange", "symbol"],
)
market_data_staleness = Gauge(
    "pensy_market_data_staleness_seconds",
    "Age of latest market data",
    ["symbol"],
)

# API metrics
api_request_duration = Histogram(
    "pensy_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint", "status_code"],
)

# Agent / Skill metrics
skill_executions = Counter(
    "pensy_skill_executions_total",
    "Total skill executions",
    ["skill_id", "agent_type", "status", "execution_type"],
)
skill_duration = Histogram(
    "pensy_skill_execution_duration_seconds",
    "Skill execution duration",
    ["skill_id", "execution_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
agent_pipeline_duration = Histogram(
    "pensy_agent_pipeline_duration_seconds",
    "Agent pipeline total duration",
    ["agent_type"],
)
agent_pipeline_failures = Counter(
    "pensy_agent_pipeline_failures_total",
    "Agent pipeline failures",
    ["agent_type", "reason"],
)

"""
Domain enumerations for the Pensy platform.

These enums define the canonical vocabulary for the entire system.
All modules reference these enums rather than raw strings.
"""

from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LIMIT = "STOP_LIMIT"
    STOP_MARKET = "STOP_MARKET"


class TimeInForce(str, Enum):
    GTC = "GTC"  # Good til cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    GTD = "GTD"  # Good til date


class OrderStatus(str, Enum):
    PENDING = "PENDING"              # Created, awaiting risk check
    APPROVED = "APPROVED"            # Passed risk checks
    SUBMITTED = "SUBMITTED"          # Sent to exchange, awaiting ack
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"                # Terminal
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"          # Terminal
    REJECTED = "REJECTED"            # Terminal - rejected by risk engine
    EXCHANGE_REJECTED = "EXCHANGE_REJECTED"  # Terminal - rejected by exchange
    EXPIRED = "EXPIRED"              # Terminal
    FAILED = "FAILED"                # Terminal - system failure

    @property
    def is_terminal(self) -> bool:
        return self in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXCHANGE_REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        }

    @property
    def is_active(self) -> bool:
        return self in {
            OrderStatus.PENDING,
            OrderStatus.APPROVED,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }


class TradingMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"


class ExchangeName(str, Enum):
    PAPER = "paper"
    BINANCE_SPOT = "binance_spot"
    BINANCE_FUTURES = "binance_futures"
    ALPACA = "alpaca"
    FOREX_SIM = "forex_sim"


class RiskSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskCheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"  # Check not applicable


class ExchangeConnectivityState(str, Enum):
    CONNECTED = "CONNECTED"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class StrategyType(str, Enum):
    TWAP = "TWAP"
    MARKET_MAKING = "MARKET_MAKING"
    ARBITRAGE = "ARBITRAGE"


class ReconciliationStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReconciliationBreakType(str, Enum):
    POSITION_MISMATCH = "POSITION_MISMATCH"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"
    UNKNOWN_ORDER = "UNKNOWN_ORDER"
    MISSING_ORDER = "MISSING_ORDER"
    STATUS_MISMATCH = "STATUS_MISMATCH"


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class AuditAction(str, Enum):
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FILLED = "ORDER_FILLED"
    STRATEGY_ENABLED = "STRATEGY_ENABLED"
    STRATEGY_DISABLED = "STRATEGY_DISABLED"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_DEACTIVATED = "KILL_SWITCH_DEACTIVATED"
    LIVE_MODE_CONFIRMED = "LIVE_MODE_CONFIRMED"
    RISK_LIMIT_BREACH = "RISK_LIMIT_BREACH"
    RECONCILIATION_RUN = "RECONCILIATION_RUN"
    USER_LOGIN = "USER_LOGIN"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    MANUAL_ORDER = "MANUAL_ORDER"

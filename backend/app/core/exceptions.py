"""
Domain exception hierarchy for the Pensy platform.

All exceptions inherit from PensyError for catch-all handling.
Specific exceptions enable targeted error handling and meaningful API responses.
"""


class PensyError(Exception):
    """Base exception for all Pensy platform errors."""

    def __init__(self, message: str, code: str = "PENSY_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


# --- Order Errors ---


class OrderError(PensyError):
    """Base for order-related errors."""

    def __init__(self, message: str, code: str = "ORDER_ERROR"):
        super().__init__(message, code)


class InvalidStateTransition(OrderError):
    """Attempted illegal order state transition."""

    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            f"Invalid state transition: {current_status} -> {target_status}",
            code="INVALID_STATE_TRANSITION",
        )
        self.current_status = current_status
        self.target_status = target_status


class DuplicateOrder(OrderError):
    """Order with this client_order_id already exists."""

    def __init__(self, client_order_id: str):
        super().__init__(
            f"Duplicate order: client_order_id={client_order_id}",
            code="DUPLICATE_ORDER",
        )


class OrderNotFound(OrderError):
    """Order not found in the system."""

    def __init__(self, order_id: str):
        super().__init__(f"Order not found: {order_id}", code="ORDER_NOT_FOUND")


# --- Risk Errors ---


class RiskError(PensyError):
    """Base for risk-related errors."""

    def __init__(self, message: str, code: str = "RISK_ERROR"):
        super().__init__(message, code)


class RiskCheckFailed(RiskError):
    """One or more risk checks failed."""

    def __init__(self, failures: list[dict]):
        self.failures = failures
        names = [f["check_name"] for f in failures]
        super().__init__(
            f"Risk check failed: {', '.join(names)}",
            code="RISK_CHECK_FAILED",
        )


class KillSwitchActive(RiskError):
    """Global kill switch is active, all orders blocked."""

    def __init__(self) -> None:
        super().__init__("Kill switch is active. All orders blocked.", code="KILL_SWITCH_ACTIVE")


# --- Exchange Errors ---


class ExchangeError(PensyError):
    """Base for exchange-related errors."""

    def __init__(self, message: str, exchange: str = "", code: str = "EXCHANGE_ERROR"):
        self.exchange = exchange
        super().__init__(f"[{exchange}] {message}" if exchange else message, code)


class ExchangeConnectionError(ExchangeError):
    """Cannot connect to exchange."""

    def __init__(self, exchange: str, detail: str = ""):
        super().__init__(f"Connection failed: {detail}", exchange, "EXCHANGE_CONNECTION_ERROR")


class ExchangeRateLimited(ExchangeError):
    """Exchange rate limit hit."""

    def __init__(self, exchange: str, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s", exchange, "RATE_LIMITED")


class ExchangeOrderRejected(ExchangeError):
    """Exchange rejected the order."""

    def __init__(self, exchange: str, reason: str, exchange_code: str = ""):
        self.reason = reason
        self.exchange_code = exchange_code
        super().__init__(f"Order rejected: {reason}", exchange, "EXCHANGE_ORDER_REJECTED")


# --- Trading Mode Errors ---


class TradingModeError(PensyError):
    """Error related to trading mode configuration."""

    def __init__(self, message: str):
        super().__init__(message, code="TRADING_MODE_ERROR")


class LiveTradingNotEnabled(TradingModeError):
    """Attempted live trading without proper configuration."""

    def __init__(self) -> None:
        super().__init__(
            "Live trading is not enabled. Set LIVE_TRADING_ENABLED=true "
            "and confirm via admin API."
        )


# --- Strategy Errors ---


class StrategyError(PensyError):
    """Base for strategy-related errors."""

    def __init__(self, message: str, code: str = "STRATEGY_ERROR"):
        super().__init__(message, code)


# --- Reconciliation Errors ---


class ReconciliationError(PensyError):
    """Base for reconciliation-related errors."""

    def __init__(self, message: str, code: str = "RECONCILIATION_ERROR"):
        super().__init__(message, code)


# --- Auth Errors ---


class AuthError(PensyError):
    """Base for authentication/authorization errors."""

    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        super().__init__(message, code)


class InvalidCredentials(AuthError):
    def __init__(self) -> None:
        super().__init__("Invalid credentials", code="INVALID_CREDENTIALS")


class InsufficientPermissions(AuthError):
    def __init__(self, action: str = ""):
        super().__init__(
            f"Insufficient permissions{': ' + action if action else ''}",
            code="INSUFFICIENT_PERMISSIONS",
        )


# --- Agent / Skill Errors ---


class AgentError(PensyError):
    """Base for agent-related errors."""

    def __init__(self, message: str, code: str = "AGENT_ERROR"):
        super().__init__(message, code)


class SkillNotFound(AgentError):
    def __init__(self, skill_id: str):
        super().__init__(f"Skill not found: {skill_id}", code="SKILL_NOT_FOUND")


class SkillDisabled(AgentError):
    def __init__(self, skill_id: str):
        super().__init__(f"Skill is disabled: {skill_id}", code="SKILL_DISABLED")


class AgentPipelineError(AgentError):
    def __init__(self, agent_type: str, reason: str):
        super().__init__(
            f"Agent pipeline error [{agent_type}]: {reason}",
            code="PIPELINE_ERROR",
        )

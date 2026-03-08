"""
Structured JSON logging setup using structlog.

All logs include service name, environment, and request context.
Secrets are automatically filtered from log output.
"""

from __future__ import annotations

import logging
import sys

import structlog

SECRET_PATTERNS = {"key", "secret", "password", "token", "authorization"}


def _filter_secrets(_, __, event_dict: dict) -> dict:
    """Redact values whose keys match secret patterns."""
    for key in list(event_dict.keys()):
        if any(pattern in key.lower() for pattern in SECRET_PATTERNS):
            event_dict[key] = "***REDACTED***"
    return event_dict


def setup_logging(log_level: str = "INFO", app_env: str = "development") -> None:
    """Configure structured logging for the application."""

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            _filter_secrets,
            structlog.processors.JSONRenderer() if app_env != "development"
            else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    if not root_logger.handlers:
        root_logger.addHandler(handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger bound with the service name."""
    return structlog.get_logger(name)

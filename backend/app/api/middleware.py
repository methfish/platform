"""
FastAPI middleware for the Pensy platform.

Provides:
- RequestIdMiddleware: Attaches a unique X-Request-ID to every request/response
  and stores it in contextvars for downstream correlation logging.
- TimingMiddleware: Logs the wall-clock duration of every request.
- pensy_error_handler: Converts PensyError exceptions into structured JSON
  error responses.
"""

from __future__ import annotations

import contextvars
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.exceptions import (
    AuthError,
    InvalidCredentials,
    InsufficientPermissions,
    OrderNotFound,
    PensyError,
    KillSwitchActive,
    ExchangeRateLimited,
)

logger = logging.getLogger("pensy.middleware")

# Context variable holding the current request id for structured logging.
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assign a unique UUID to every incoming request.

    The id is stored in ``request_id_ctx`` and added as the
    ``X-Request-ID`` response header for client-side correlation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid4())
        request_id_ctx.set(rid)
        request.state.request_id = rid

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Log the wall-clock duration of each HTTP request and expose it via
    the ``X-Process-Time`` response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        logger.info(
            "%s %s completed in %.2fms (status=%d)",
            request.method,
            request.url.path,
            elapsed_ms,
            response.status_code,
        )
        return response


# ---------------------------------------------------------------------------
# Exception -> HTTP status mapping
# ---------------------------------------------------------------------------

_ERROR_STATUS_MAP: dict[type, int] = {
    InvalidCredentials: 401,
    AuthError: 401,
    InsufficientPermissions: 403,
    OrderNotFound: 404,
    KillSwitchActive: 423,
    ExchangeRateLimited: 429,
}


async def pensy_error_handler(request: Request, exc: PensyError) -> JSONResponse:
    """
    Convert any ``PensyError`` (or subclass) into a structured JSON response
    with the appropriate HTTP status code.
    """
    status_code = 400
    for exc_type, code in _ERROR_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            status_code = code
            break

    rid = getattr(request.state, "request_id", None) or request_id_ctx.get("")

    body: dict = {
        "error": {
            "code": exc.code,
            "message": exc.message,
        }
    }
    if rid:
        body["error"]["request_id"] = rid

    logger.warning(
        "PensyError [%s] %s (status=%d, request_id=%s)",
        exc.code,
        exc.message,
        status_code,
        rid,
    )

    return JSONResponse(status_code=status_code, content=body)


def register_middleware(app: FastAPI) -> None:
    """
    Convenience function to wire all middleware and exception handlers onto
    the FastAPI application instance.
    """
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_exception_handler(PensyError, pensy_error_handler)  # type: ignore[arg-type]

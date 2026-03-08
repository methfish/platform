"""
JWT token creation and verification for Pensy platform authentication.

Uses python-jose for JWT encoding/decoding and integrates with FastAPI's
dependency injection for extracting the current user from Bearer tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import AuthError, InvalidCredentials
from app.db.session import get_session
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    settings: Settings | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Claims to encode in the token. Must include ``sub`` (subject / user id).
        expires_delta: Custom expiration period. Falls back to config default.
        settings: Optional settings override (useful for testing).

    Returns:
        Encoded JWT string.
    """
    s = settings or get_settings()
    to_encode = data.copy()

    if expires_delta is None:
        expires_delta = timedelta(minutes=s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    return jwt.encode(
        to_encode,
        s.JWT_SECRET_KEY.get_secret_value(),
        algorithm=s.JWT_ALGORITHM,
    )


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: Raw JWT string.
        settings: Optional settings override.

    Returns:
        Decoded claims dict.

    Raises:
        AuthError: If the token is expired, malformed, or signature is invalid.
    """
    s = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            s.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[s.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise AuthError(f"Invalid token: {exc}", code="INVALID_TOKEN")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    """
    FastAPI dependency that extracts and validates the current user from a
    Bearer token in the Authorization header.

    Returns:
        The authenticated User ORM instance.

    Raises:
        AuthError: If no token is provided, or the token is invalid.
        InvalidCredentials: If the user referenced by the token does not exist
            or is inactive.
    """
    if credentials is None:
        raise AuthError("Missing authorization header", code="MISSING_TOKEN")

    payload = decode_token(credentials.credentials, settings)

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise AuthError("Token missing 'sub' claim", code="INVALID_TOKEN")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise AuthError("Invalid user id in token", code="INVALID_TOKEN")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidCredentials()

    if not user.is_active:
        raise AuthError("User account is disabled", code="USER_DISABLED")

    return user

"""
Authentication endpoints: login and user registration.

POST /auth/login   - Validate credentials, return a JWT.
POST /auth/register - Create a new user (admin only).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.jwt import create_access_token, get_current_user
from app.auth.password import hash_password, verify_password
from app.auth.permissions import require_role
from app.core.enums import UserRole
from app.core.exceptions import AuthError, InvalidCredentials
from app.db.session import get_session
from app.models.user import User

logger = logging.getLogger("pensy.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain a JWT",
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Validate username/password credentials and return a signed JWT access
    token on success.
    """
    result = await session.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise InvalidCredentials()

    if not user.is_active:
        raise AuthError("User account is disabled", code="USER_DISABLED")

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    logger.info("User %s logged in successfully", user.username)
    return TokenResponse(access_token=token)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin only)",
)
async def register(
    body: RegisterRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """
    Create a new platform user. Only administrators may call this endpoint.
    """
    # Check for existing username or email
    existing = await session.execute(
        select(User).where(
            (User.username == body.username) | (User.email == body.email)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AuthError(
            "Username or email already exists", code="USER_ALREADY_EXISTS"
        )

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    logger.info(
        "Admin %s created user %s with role %s",
        current_user.username,
        user.username,
        user.role,
    )
    return UserResponse.model_validate(user)

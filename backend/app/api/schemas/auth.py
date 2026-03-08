"""
Pydantic request/response schemas for authentication endpoints.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials for user login."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Payload for creating a new user (admin-only)."""

    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="VIEWER", pattern="^(ADMIN|OPERATOR|VIEWER)$")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user details (no password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: str
    is_active: bool

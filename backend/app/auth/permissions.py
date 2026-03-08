"""
Role-based permission checks for the Pensy platform.

Provides a simple FastAPI dependency factory that enforces minimum role
requirements on route handlers.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from app.auth.jwt import get_current_user
from app.core.enums import UserRole
from app.core.exceptions import InsufficientPermissions
from app.models.user import User

# Role hierarchy: ADMIN > OPERATOR > VIEWER
_ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.VIEWER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ADMIN: 2,
}


def require_role(required_role: UserRole) -> Callable:
    """
    Return a FastAPI dependency that ensures the authenticated user has at
    least the specified role level.

    Usage::

        @router.post("/admin/action")
        async def admin_action(
            user: User = Depends(require_role(UserRole.ADMIN)),
        ):
            ...

    Args:
        required_role: The minimum role the user must possess.

    Returns:
        A dependency callable that yields the authenticated User if
        authorized, or raises InsufficientPermissions.
    """

    async def _check_role(user: User = Depends(get_current_user)) -> User:
        user_role = UserRole(user.role)
        if _ROLE_HIERARCHY.get(user_role, -1) < _ROLE_HIERARCHY[required_role]:
            raise InsufficientPermissions(
                f"Requires role {required_role.value}, user has {user.role}"
            )
        return user

    return _check_role

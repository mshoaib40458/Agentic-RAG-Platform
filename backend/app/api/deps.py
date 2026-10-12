"""Reusable FastAPI dependencies: DB session, auth, RBAC, pagination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROLE_PERMISSIONS, Permission, UserRole
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_session
from app.repositories.user_repo import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("A bearer token is required.")
    claims = decode_token(credentials.credentials, expected_type="access")
    user = await UserRepository(session).get(claims["sub"])
    if user is None:
        raise AuthenticationError("The account for this token no longer exists.")
    if not user.is_active:
        raise AuthenticationError("This account is disabled.", code="account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: Permission):
    """Dependency factory enforcing role-based permissions (SRS FR-002)."""

    async def _dependency(user: CurrentUser) -> User:
        try:
            role = UserRole(user.role)
        except ValueError:
            raise PermissionDeniedError("Unknown role.") from None
        if permission not in ROLE_PERMISSIONS.get(role, frozenset()):
            raise PermissionDeniedError(f"Missing required permission: {permission.value}")
        return user

    return _dependency


@dataclass(slots=True)
class Pagination:
    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(get_pagination)]

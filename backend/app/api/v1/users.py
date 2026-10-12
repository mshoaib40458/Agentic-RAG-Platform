"""User administration endpoints (SRS FR-002)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import PaginationDep, SessionDep, require_permission
from app.core.constants import Permission
from app.db.models.user import User
from app.schemas.auth import UserRead, UserUpdate
from app.schemas.common import Page
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])

AdminDep = Annotated[User, Depends(require_permission(Permission.USERS_MANAGE))]


@router.get("", response_model=Page[UserRead])
async def list_users(
    session: SessionDep, pagination: PaginationDep, _: AdminDep
) -> Page[UserRead]:
    items, total = await AuthService(session).list_users(
        limit=pagination.limit, offset=pagination.offset
    )
    return Page(items=items, total=total, limit=pagination.limit, offset=pagination.offset)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str, payload: UserUpdate, session: SessionDep, _: AdminDep
) -> UserRead:
    service = AuthService(session)
    user = await service.get_user(user_id)
    if payload.role is not None:
        user.role = payload.role.value
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await session.flush()
    return UserRead.model_validate(user)

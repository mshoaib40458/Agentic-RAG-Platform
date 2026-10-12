"""Authentication endpoints (SRS FR-001/FR-005)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.core.constants import UserRole
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, Token, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: SessionDep) -> UserRead:
    """Register a user.

    The first account created bootstraps the system as an administrator. All
    subsequent self-registrations are forced to the ``user`` role to prevent
    privilege escalation; admins assign other roles via ``/users``.
    """
    users = UserRepository(session)
    is_first_user = await users.count() == 0
    if is_first_user:
        payload = payload.model_copy(update={"role": UserRole.ADMIN})
    else:
        payload = payload.model_copy(update={"role": UserRole.USER})
    user = await AuthService(session).register(payload)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, session: SessionDep) -> Token:
    service = AuthService(session)
    user = await service.authenticate(payload.username, payload.password)
    return service.issue_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, session: SessionDep) -> Token:
    return await AuthService(session).refresh(payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)

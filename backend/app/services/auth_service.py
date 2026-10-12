"""Authentication and user-management business logic."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import Token, UserCreate, UserRead


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.users.exists(email=data.email, username=data.username):
            raise ConflictError("Email or username is already registered.")
        user = User(
            email=data.email.lower(),
            username=data.username,
            hashed_password=hash_password(data.password),
            role=data.role.value,
        )
        return await self.users.add(user)

    async def authenticate(self, identifier: str, password: str) -> User:
        user = await self.users.get_by_login(identifier)
        # Constant-ish behavior: always run a verify to reduce user enumeration.
        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid username or password.")
        if not user.is_active:
            raise AuthenticationError("This account is disabled.", code="account_disabled")
        return user

    def issue_tokens(self, user: User) -> Token:
        settings = get_settings()
        return Token(
            access_token=create_access_token(user.id, role=user.role),
            refresh_token=create_refresh_token(user.id, role=user.role),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> Token:
        claims = decode_token(refresh_token, expected_type="refresh")
        user = await self.users.get(claims["sub"])
        if user is None or not user.is_active:
            raise AuthenticationError("The account is unavailable.", code="account_unavailable")
        return self.issue_tokens(user)

    async def get_user(self, user_id: str) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def list_users(self, *, limit: int, offset: int) -> tuple[list[UserRead], int]:
        users = await self.users.list(limit=limit, offset=offset, order_by=User.created_at.desc())
        total = await self.users.count()
        return [UserRead.model_validate(user) for user in users], total

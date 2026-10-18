"""Authentication and user-management business logic."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import UserRole
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

# A fixed valid Argon2id hash used to maintain constant verification time when
# a user is not found, mitigating username enumeration via timing analysis.
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$RdescudvJCsgqlfreOJRomIMacPdIhBs"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: UserCreate) -> User:
        if await self.users.exists(email=data.email, username=data.username):
            raise ConflictError("Email or username is already registered.")
        role = data.role.value
        if role == UserRole.ADMIN.value:
            # Defense-in-depth: only permit admin bootstrap if no admin exists yet
            existing_admin = await self.users.get_first_admin()
            if existing_admin is not None:
                role = UserRole.USER.value
        user = User(
            email=data.email.lower(),
            username=data.username,
            hashed_password=hash_password(data.password),
            role=role,
        )
        return await self.users.add(user)

    async def authenticate(self, identifier: str, password: str) -> User:
        user = await self.users.get_by_login(identifier)
        # Always run verify_password to ensure constant-time response and prevent user enumeration
        target_hash = user.hashed_password if user is not None else _DUMMY_HASH
        is_valid = verify_password(password, target_hash)
        if user is None or not is_valid:
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

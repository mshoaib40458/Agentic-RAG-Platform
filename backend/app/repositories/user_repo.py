"""User repository."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.db.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_login(self, identifier: str) -> User | None:
        stmt = select(User).where(
            or_(User.email == identifier.lower(), User.username == identifier)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists(self, *, email: str | None = None, username: str | None = None) -> bool:
        clauses = []
        if email:
            clauses.append(User.email == email.lower())
        if username:
            clauses.append(User.username == username)
        if not clauses:
            return False
        stmt = select(User.id).where(or_(*clauses)).limit(1)
        return (await self.session.execute(stmt)).first() is not None

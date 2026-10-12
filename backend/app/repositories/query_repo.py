"""Query and Answer repositories."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.query import Answer, Query
from app.repositories.base import BaseRepository


class QueryRepository(BaseRepository[Query]):
    model = Query

    async def get_with_answer(self, query_id: str) -> Query | None:
        stmt = (
            select(Query)
            .where(Query.id == query_id)
            .options(selectinload(Query.answer))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self, *, user_id: str, limit: int = 50, offset: int = 0, include_all: bool = False
    ) -> tuple[list[Query], int]:
        stmt = select(Query).options(selectinload(Query.answer)).order_by(Query.created_at.desc())
        count_stmt = select(func.count()).select_from(Query)
        if not include_all:
            stmt = stmt.where(Query.user_id == user_id)
            count_stmt = count_stmt.where(Query.user_id == user_id)
        stmt = stmt.limit(limit).offset(offset)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return rows, total

    async def add_answer(self, answer: Answer) -> Answer:
        self.session.add(answer)
        await self.session.flush()
        return answer

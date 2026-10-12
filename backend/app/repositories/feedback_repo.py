"""Feedback repository."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.models.feedback import Feedback
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    model = Feedback

    async def for_query(self, query_id: str) -> list[Feedback]:
        stmt = select(Feedback).where(Feedback.query_id == query_id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for_user_and_query(self, *, user_id: str, query_id: str) -> Feedback | None:
        stmt = select(Feedback).where(
            Feedback.user_id == user_id, Feedback.query_id == query_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def summary_for_query(self, query_id: str) -> dict[str, int]:
        stmt = (
            select(Feedback.rating, func.count())
            .where(Feedback.query_id == query_id)
            .group_by(Feedback.rating)
        )
        rows = (await self.session.execute(stmt)).all()
        positive = sum(int(count) for rating, count in rows if rating > 0)
        negative = sum(int(count) for rating, count in rows if rating < 0)
        return {"positive": positive, "negative": negative}

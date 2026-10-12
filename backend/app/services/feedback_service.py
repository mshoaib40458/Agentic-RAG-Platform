"""Answer feedback business logic (SRS FR-047)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.core.exceptions import NotFoundError
from app.db.models.feedback import Feedback
from app.db.models.user import User
from app.repositories.feedback_repo import FeedbackRepository
from app.repositories.query_repo import QueryRepository
from app.schemas.evaluation import FeedbackCreate


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.feedback = FeedbackRepository(session)
        self.queries = QueryRepository(session)

    async def submit(self, data: FeedbackCreate, *, user: User) -> Feedback:
        query = await self.queries.get(data.query_id)
        if query is None:
            raise NotFoundError("Query not found.")
        can_view_all = user.role == UserRole.ADMIN.value
        if query.user_id != user.id and not can_view_all:
            raise NotFoundError("Query not found.")

        existing = await self.feedback.get_for_user_and_query(user_id=user.id, query_id=query.id)
        if existing is not None:
            # Update-in-place keeps one rating per user per query.
            existing.rating = data.rating
            existing.comment = data.comment
            await self.session.flush()
            return existing

        feedback = Feedback(
            user_id=user.id, query_id=query.id, rating=data.rating, comment=data.comment
        )
        return await self.feedback.add(feedback)

    async def list_for_query(self, query_id: str, *, user: User) -> list[Feedback]:
        query = await self.queries.get(query_id)
        if query is None:
            raise NotFoundError("Query not found.")
        return await self.feedback.for_query(query_id)

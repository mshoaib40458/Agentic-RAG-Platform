"""Conversation data-access (chat threads and their turns)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.conversation import Conversation, ConversationTurn
from app.db.models.query import Query
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def list_for_user(
        self, *, user_id: str, include_all: bool = False, limit: int = 50, offset: int = 0
    ) -> tuple[list[Conversation], int]:
        stmt = select(Conversation).order_by(Conversation.updated_at.desc())
        count_stmt = select(func.count()).select_from(Conversation)
        if not include_all:
            stmt = stmt.where(Conversation.user_id == user_id)
            count_stmt = count_stmt.where(Conversation.user_id == user_id)
        stmt = stmt.limit(limit).offset(offset)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return rows, total

    async def recent_turns(
        self, conversation_id: str, *, limit: int
    ) -> list[ConversationTurn]:
        stmt = (
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation_id)
            .order_by(ConversationTurn.created_at.desc())
            .options(
                selectinload(ConversationTurn.query).selectinload(Query.answer)
            )
        )
        if limit > 0:
            stmt = stmt.limit(limit)
        turns = list((await self.session.execute(stmt)).scalars().all())
        turns.reverse()
        return turns

    async def turn_counts(self, conversation_ids: list[str]) -> dict[str, int]:
        if not conversation_ids:
            return {}
        stmt = (
            select(ConversationTurn.conversation_id, func.count())
            .where(ConversationTurn.conversation_id.in_(conversation_ids))
            .group_by(ConversationTurn.conversation_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows}

    async def get_with_turns(self, conversation_id: str) -> Conversation | None:
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.turns)
                .selectinload(ConversationTurn.query)
                .selectinload(Query.answer)
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_turn(self, *, conversation_id: str, query_id: str) -> ConversationTurn:
        turn = ConversationTurn(conversation_id=conversation_id, query_id=query_id)
        self.session.add(turn)
        await self.session.flush()
        return turn

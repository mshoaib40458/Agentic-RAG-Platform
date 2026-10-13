"""Conversation lifecycle and chat-history assembly (SRS 4.4).

Conversations group the queries that make up a chat so follow-up questions can
be resolved against earlier turns (conversational query understanding).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import UserRole
from app.core.exceptions import NotFoundError
from app.db.models.conversation import Conversation, ConversationTurn
from app.db.models.query import Query
from app.db.models.user import User
from app.repositories.conversation_repo import ConversationRepository

_DEFAULT_TITLE = "New chat"


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.conversations = ConversationRepository(session)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def create(self, *, user: User, title: str | None = None) -> Conversation:
        now = datetime.now(UTC)
        conversation = Conversation(
            user_id=user.id,
            title=(title or "").strip() or "New chat",
            created_at=now,
            updated_at=now,
        )
        await self.conversations.add(conversation)
        return conversation

    async def get(self, conversation_id: str, *, user: User) -> Conversation:
        conversation = await self.conversations.get_with_turns(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        can_view_all = user.role in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
        if conversation.user_id != user.id and not can_view_all:
            raise NotFoundError("Conversation not found.")
        return conversation

    async def delete(self, conversation_id: str, *, user: User) -> None:
        conversation = await self.conversations.get(conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise NotFoundError("Conversation not found.")
        await self.conversations.delete(conversation)

    async def resolve(
        self, *, user: User, conversation_id: str | None, question: str
    ) -> Conversation:
        """Load the target conversation (with its turns) or start a new chat."""
        if conversation_id:
            return await self.get(conversation_id, user=user)
        return await self.create(user=user, title=question.strip()[:60])

    async def list_conversations(
        self, *, user: User, limit: int = 50, offset: int = 0
    ) -> tuple[list[tuple[Conversation, int]], int]:
        include_all = user.role in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
        rows, total = await self.conversations.list_for_user(
            user_id=user.id, include_all=include_all, limit=limit, offset=offset
        )
        counts = await self.conversations.turn_counts([row.id for row in rows])
        return [(row, counts.get(row.id, 0)) for row in rows], total

    async def attach_turn(self, conversation: Conversation, query: Query) -> None:
        await self.conversations.add_turn(conversation_id=conversation.id, query_id=query.id)
        if conversation.title.strip().lower() in {"", "new chat"}:
            conversation.title = query.question.strip()[:60] or "New chat"
        conversation.updated_at = datetime.now(UTC)

    @staticmethod
    def _to_history(turns: list[ConversationTurn]) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        for turn in turns:
            query = turn.query
            if query is None:
                continue
            answer = query.answer
            history.append(
                {
                    "question": query.question,
                    "answer": answer.content if answer is not None else "",
                }
            )
        return history

    async def history_for(
        self, conversation: Conversation, *, limit: int
    ) -> list[dict[str, str]]:
        """Return the last ``limit`` completed turns, oldest-first."""
        turns = await self.conversations.recent_turns(conversation.id, limit=limit)
        return self._to_history(turns)

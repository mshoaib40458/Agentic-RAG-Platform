"""Conversation and turn models for multi-turn chat (SRS 4.4).

A conversation is an ordered set of turns; each turn links one :class:`Query`
(and, through it, its answer). The join table keeps ``queries`` untouched, so
existing databases gain chat support without altering the ``queries`` table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.query import Query
    from app.db.models.user import User


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), default="New chat", nullable=False)

    user: Mapped[User] = relationship(back_populates="conversations")
    turns: Mapped[list[ConversationTurn]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationTurn.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Conversation id={self.id} title={self.title!r}>"


class ConversationTurn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_turns"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    query_id: Mapped[str] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), index=True, unique=True, nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="turns")
    query: Mapped[Query] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ConversationTurn conversation_id={self.conversation_id} "
            f"query_id={self.query_id}>"
        )

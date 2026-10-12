"""Answer feedback model (SRS FR-047)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.query import Query
    from app.db.models.user import User


class Feedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating IN (-1, 1)", name="rating_valid"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    query_id: Mapped[str] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # thumbs down (-1) / up (1)
    comment: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="feedback")
    query: Mapped[Query] = relationship(back_populates="feedback")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Feedback id={self.id} query_id={self.query_id} rating={self.rating}>"

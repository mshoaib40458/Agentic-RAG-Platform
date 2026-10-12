"""Document repository, including access-scoped queries.

Access model (initial release, SRS FR-002/FR-004/FR-027):

* ``ADMIN`` users can read every document.
* Every other role can read documents they own **or** that live in the reserved
  public collection (``PUBLIC_COLLECTION``).

This keeps isolation-by-default while allowing a shared knowledge base. It is
the single place where document visibility is decided.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.core.constants import DocumentStatus, UserRole
from app.db.models.document import Document, DocumentChunk
from app.repositories.base import BaseRepository

PUBLIC_COLLECTION = "public"


def _access_condition(user_id: str, role: str):
    if role == UserRole.ADMIN.value:
        return None
    return or_(Document.owner_id == user_id, Document.collection == PUBLIC_COLLECTION)


class DocumentRepository(BaseRepository[Document]):
    model = Document

    def _visibility(self, user_id: str, role: str):
        condition = _access_condition(user_id, role)
        return [] if condition is None else [condition]

    async def get_accessible(self, document_id: str, *, user_id: str, role: str) -> Document | None:
        stmt = select(Document).where(Document.id == document_id)
        condition = _access_condition(user_id, role)
        if condition is not None:
            stmt = stmt.where(condition)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_checksum(self, *, owner_id: str, checksum: str) -> Document | None:
        stmt = select(Document).where(
            Document.owner_id == owner_id, Document.checksum == checksum
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _conditions(
        self,
        *,
        user_id: str,
        role: str,
        category: str | None = None,
        collection: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> list:
        conditions = self._visibility(user_id, role)
        if category:
            conditions.append(Document.category == category)
        if collection:
            conditions.append(Document.collection == collection)
        if status:
            conditions.append(Document.status == status)
        if search:
            conditions.append(Document.filename.ilike(f"%{search}%"))
        return conditions

    async def list_accessible(
        self,
        *,
        user_id: str,
        role: str,
        category: str | None = None,
        collection: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        conditions = self._conditions(
            user_id=user_id,
            role=role,
            category=category,
            collection=collection,
            status=status,
            search=search,
        )
        stmt = select(Document)
        count_stmt = select(func.count()).select_from(Document)
        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))
        stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)

        rows = list((await self.session.execute(stmt)).scalars().all())
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return rows, total

    async def accessible_document_ids(self, *, user_id: str, role: str) -> list[str]:
        """Return ids of documents the user may retrieve from (SRS FR-027)."""
        stmt = select(Document.id).where(Document.status == DocumentStatus.INDEXED.value)
        condition = _access_condition(user_id, role)
        if condition is not None:
            stmt = stmt.where(condition)
        return list((await self.session.execute(stmt)).scalars().all())

    async def stats(self, *, user_id: str, role: str) -> dict[str, int]:
        visibility = self._visibility(user_id, role)
        stmt = select(Document.status, func.count()).group_by(Document.status)
        if visibility:
            stmt = stmt.where(and_(*visibility))
        rows = (await self.session.execute(stmt)).all()
        by_status = {status: int(count) for status, count in rows}

        chunk_stmt = select(func.count(DocumentChunk.id)).join(
            Document, DocumentChunk.document_id == Document.id
        )
        if visibility:
            chunk_stmt = chunk_stmt.where(and_(*visibility))
        total_chunks = int((await self.session.execute(chunk_stmt)).scalar_one())

        return {
            "total": sum(by_status.values()),
            "indexed": by_status.get(DocumentStatus.INDEXED.value, 0),
            "processing": by_status.get(DocumentStatus.PROCESSING.value, 0),
            "queued": by_status.get(DocumentStatus.QUEUED.value, 0),
            "failed": by_status.get(DocumentStatus.FAILED.value, 0),
            "total_chunks": total_chunks,
        }

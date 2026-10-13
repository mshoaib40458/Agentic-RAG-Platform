"""Document ingestion and management business logic (SRS 4.2)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.constants import DocumentStatus, UserRole
from app.core.exceptions import (
    DuplicateDocumentError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.db.models.document import Document
from app.db.models.user import User
from app.ingestion.pipeline import DocumentIngestor
from app.repositories.document_repo import DocumentRepository
from app.repositories.query_repo import QueryRepository
from app.retrieval import bm25
from app.schemas.document import DocumentStats, DocumentUpdate

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.documents = DocumentRepository(session)

    # ------------------------------------------------------------------ #
    # Upload / ingestion
    # ------------------------------------------------------------------ #
    async def create_document(
        self,
        *,
        upload: UploadFile,
        owner: User,
        category: str | None = None,
        collection: str = "default",
    ) -> Document:
        original_name = Path(upload.filename or "upload").name
        extension = Path(original_name).suffix.lower()
        if extension not in self.settings.allowed_extensions_set:
            raise UnsupportedMediaTypeError(
                f"Unsupported file type '{extension or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(self.settings.allowed_extensions_set))}."
            )

        self.settings.ensure_directories()
        stored_path = self.settings.upload_path / f"{uuid.uuid4().hex}{extension}"
        try:
            size_bytes, checksum = await self._stream_to_disk(upload, stored_path)
        except PayloadTooLargeError:
            stored_path.unlink(missing_ok=True)
            raise

        existing = await self.documents.get_by_checksum(owner_id=owner.id, checksum=checksum)
        if existing is not None:
            stored_path.unlink(missing_ok=True)
            raise DuplicateDocumentError(
                details={"existing_document_id": existing.id, "filename": existing.filename}
            )

        document = Document(
            filename=original_name,
            file_type=extension,
            content_type=upload.content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            storage_path=str(stored_path),
            owner_id=owner.id,
            collection=collection,
            category=category,
            status=DocumentStatus.QUEUED.value,
        )
        await self.documents.add(document)

        ingestor = DocumentIngestor(self.session)
        await ingestor.run(document)
        await self.session.refresh(document)
        bm25.invalidate()
        return document

    async def _stream_to_disk(self, upload: UploadFile, dest: Path) -> tuple[int, str]:
        hasher = hashlib.sha256()
        total = 0
        max_bytes = self.settings.max_upload_bytes
        with dest.open("wb") as handle:
            while chunk := await upload.read(_CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise PayloadTooLargeError(
                        f"File exceeds the {self.settings.max_upload_mb} MB limit."
                    )
                hasher.update(chunk)
                handle.write(chunk)
        if total == 0:
            raise UnsupportedMediaTypeError("The uploaded file is empty.", code="empty_file")
        return total, hasher.hexdigest()

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def list_documents(
        self,
        *,
        user: User,
        category: str | None = None,
        collection: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        return await self.documents.list_accessible(
            user_id=user.id,
            role=user.role,
            category=category,
            collection=collection,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

    async def get_document(self, document_id: str, *, user: User) -> Document:
        document = await self.documents.get_accessible(document_id, user_id=user.id, role=user.role)
        if document is None:
            raise NotFoundError("Document not found.")
        return document

    async def stats(self, *, user: User) -> DocumentStats:
        data = await self.documents.stats(user_id=user.id, role=user.role)
        return DocumentStats(**data)

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    async def update_metadata(
        self, document_id: str, update: DocumentUpdate, *, user: User
    ) -> Document:
        document = await self.get_document(document_id, user=user)
        if user.role != UserRole.ADMIN.value and document.owner_id != user.id:
            raise NotFoundError("Document not found.")
        if update.category is not None:
            document.category = update.category
        if update.collection is not None:
            document.collection = update.collection
        await self.session.flush()
        await self.session.refresh(document)
        bm25.invalidate()
        return document

    async def delete_document(self, document_id: str, *, user: User) -> None:
        document = await self.get_document(document_id, user=user)
        if user.role != UserRole.ADMIN.value and document.owner_id != user.id:
            raise NotFoundError("Document not found.")

        from app.ingestion.pipeline import delete_document_vectors

        await delete_document_vectors(document.id)

        path = Path(document.storage_path)
        await self.documents.delete(document)
        await QueryRepository(self.session).scrub_document_references(document.id)
        await self.session.flush()
        await asyncio.to_thread(path.unlink, missing_ok=True)
        bm25.invalidate()

"""Document ingestion pipeline.

Orchestrates the full ingest lifecycle and owns its status transitions:

    QUEUED -> PROCESSING -> INDEXED
                          -> FAILED (with a user-safe error message)

Steps: extract text -> chunk (LlamaIndex) -> embed -> upsert to the vector store
-> persist chunk rows. Chunks are written to the vector store *before* the rows
are committed so a failed upsert cannot report a partial success (SRS NFR-006).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DocumentStatus
from app.core.exceptions import AppError, IngestionError
from app.db.models.document import Document, DocumentChunk
from app.ingestion.chunking import chunk_document
from app.ingestion.extractors import extract_document
from app.llm.embeddings import get_embedding_model
from app.retrieval.vector_store import VectorRecord, get_vector_store

logger = logging.getLogger(__name__)

# Stable namespace for deriving deterministic chunk ids. Changing this value
# changes every chunk id, so it must remain fixed across releases.
_CHUNK_ID_NAMESPACE = uuid.UUID("d5f3e6b0-3c2a-4b6e-9f1a-6c2d5e7a9b10")


def _chunk_identity(document_id: str, index: int) -> str:
    """Deterministic 32-char chunk id for a ``(document, position)`` pair.

    Re-ingesting the same document reproduces the same ids, which makes writes
    idempotent and prevents duplicate vectors on retries (SRS NFR-006).
    """
    return uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{document_id}:{index}").hex


def _chunk_metadata(document: Document, chunk, *, position: str) -> dict[str, object]:
    text = chunk.text
    return {
        "filename": document.filename,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "char_count": len(text),
        "word_count": len(text.split()),
        "position": position,
        "indexed_at": datetime.now(UTC).isoformat(),
    }


class DocumentIngestor:
    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_model=None,
        vector_store=None,
    ) -> None:
        self.session = session
        self.embedding_model = embedding_model or get_embedding_model()
        self.vector_store = vector_store or get_vector_store()

    async def run(self, document: Document) -> None:
        """Ingest ``document``, updating its status in place. Never raises for
        expected failures; the document is marked FAILED and the reason recorded.
        """
        document.status = DocumentStatus.PROCESSING.value
        document.error_message = None
        await self.session.commit()

        try:
            chunk_count = await self._process(document)
        except AppError as exc:
            logger.warning("ingestion_failed", extra={"document_id": document.id, "code": exc.code})
            document.status = DocumentStatus.FAILED.value
            document.error_message = exc.message
        except Exception:  # noqa: BLE001 - never leak internals to the client
            logger.exception("ingestion_unexpected_error", extra={"document_id": document.id})
            document.status = DocumentStatus.FAILED.value
            document.error_message = "Unexpected error during processing."
        else:
            document.status = DocumentStatus.INDEXED.value
            document.chunk_count = chunk_count
            document.error_message = None
        await self.session.commit()

    async def _process(self, document: Document) -> int:
        path = Path(document.storage_path)
        if not await asyncio.to_thread(path.exists):
            raise IngestionError("Stored file is missing.", code="file_missing")

        await self._clear_existing(document)

        extracted = extract_document(path, document.file_type)
        document.page_count = extracted.page_count

        chunks = chunk_document(extracted)
        if not chunks:
            raise IngestionError("No content could be chunked.", code="no_chunks")

        vectors = await self.embedding_model.embed_documents([chunk.text for chunk in chunks])

        records: list[VectorRecord] = []
        chunk_rows: list[DocumentChunk] = []
        indexed_at = datetime.now(UTC).isoformat()
        total = len(chunks)
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk_id = _chunk_identity(document.id, chunk.index)
            # Qdrant point ids must be valid UUIDs or integers. The database
            # uses a compact 32-char hex id, so map it to canonical UUID form
            # for the vector store; the payload keeps the hex chunk_id so
            # dense/BM25 results fuse on a single identifier.
            point_id = str(uuid.UUID(chunk_id))
            content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()[:16]
            if chunk.index == 0:
                position = "start"
            elif chunk.index == total - 1:
                position = "end"
            else:
                position = "middle"
            payload = {
                "document_id": document.id,
                "chunk_id": chunk_id,
                "chunk_index": chunk.index,
                "page": chunk.page,
                "filename": document.filename,
                "category": document.category,
                "collection": document.collection,
                "owner_id": document.owner_id,
                "text": chunk.text,
                "content_hash": content_hash,
                "indexed_at": indexed_at,
            }
            records.append(VectorRecord(id=point_id, vector=vector, payload=payload))
            chunk_rows.append(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document.id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    page=chunk.page,
                    token_count=chunk.token_count,
                    chunk_metadata=_chunk_metadata(document, chunk, position=position),
                    vector_id=point_id,
                )
            )

        await self.vector_store.upsert(records)
        self.session.add_all(chunk_rows)
        await self.session.flush()
        return len(chunk_rows)

    async def _clear_existing(self, document: Document) -> None:
        """Drop prior chunks/vectors so re-ingestion is idempotent.

        Deterministic chunk ids already make most upserts overwrite in place,
        but clearing first also removes stale chunks when a document shrinks.
        """
        if not document.id:
            return
        await self.vector_store.delete_by_document(document.id)
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        await self.session.flush()


async def delete_document_vectors(document_id: str) -> None:
    """Remove a document's vectors from the store (SRS FR-015)."""
    await get_vector_store().delete_by_document(document_id)

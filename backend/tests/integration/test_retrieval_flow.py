"""Integration tests for the full ingest -> retrieval flow.

Exercises the real Qdrant local vector store, the real chunking + ingestion
pipeline, and the dense/BM25/hybrid retrievers. Only the embedding model is
stubbed so the test runs without downloading ML weights.

Requires ``qdrant-client`` (a heavy dependency); skipped when unavailable.
"""

from __future__ import annotations

import hashlib
import math
import uuid

import pytest

pytest.importorskip("qdrant_client", reason="qdrant-client is not installed")

from app.core.config import get_settings  # noqa: E402
from app.db.models.document import Document  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import AsyncSessionLocal, init_db  # noqa: E402
from app.ingestion.pipeline import DocumentIngestor  # noqa: E402
from app.retrieval.bm25 import invalidate as bm25_invalidate  # noqa: E402
from app.retrieval.hybrid import HybridRetriever  # noqa: E402
from app.retrieval.vector_store import (  # noqa: E402
    get_vector_store,
    reset_vector_store,
)

DOC_LEAVE = (
    "Acme Corp Leave Policy.\n"
    "Full-time employees are entitled to twenty days of paid annual leave per "
    "calendar year. Leave accrues monthly.\n"
)
DOC_EXPENSES = (
    "Acme Corp Expense Policy.\n"
    "Travel and accommodation expenses are reimbursed when submitted within thirty "
    "days with itemized receipts.\n"
)


class _StubEmbeddingModel:
    """Deterministic pseudo-embeddings; no ML stack required."""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @staticmethod
    def _vector(text: str, dimension: int) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        buckets = [0.0] * dimension
        for index, byte in enumerate(digest):
            buckets[index % dimension] += byte / 255.0
        norm = math.sqrt(sum(value * value for value in buckets)) or 1.0
        return [value / norm for value in buckets]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:  # noqa: D102
        return [self._vector(text, self._dimension) for text in texts]

    async def embed_query(self, text: str) -> list[float]:  # noqa: D102
        return self._vector(text, self._dimension)


@pytest.fixture(autouse=True)
def _isolated_vector_store(tmp_path, monkeypatch) -> None:
    """Point Qdrant at a private path/collection for each test."""
    settings = get_settings()
    monkeypatch.setattr(settings, "qdrant_path", str(tmp_path / "qdrant"))
    monkeypatch.setattr(settings, "qdrant_collection", f"test_{uuid.uuid4().hex[:8]}")
    reset_vector_store()
    bm25_invalidate()
    yield
    reset_vector_store()
    bm25_invalidate()


async def _seed_document(
    session,
    *,
    owner_id: str,
    filename: str,
    text: str,
    category: str,
) -> Document:
    upload = get_settings().upload_path / filename
    upload.write_text(text, encoding="utf-8")
    document = Document(
        filename=filename,
        file_type=".txt",
        content_type="text/plain",
        size_bytes=len(text.encode("utf-8")),
        checksum=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        storage_path=str(upload),
        owner_id=owner_id,
        collection="default",
        category=category,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    await DocumentIngestor(session, embedding_model=_StubEmbeddingModel(384)).run(document)
    await session.refresh(document)
    assert document.status == "indexed", f"ingest failed: {document.error_message}"
    return document


async def test_ingest_then_dense_bm25_and_hybrid_retrieval():
    get_settings().ensure_directories()
    await init_db()
    async with AsyncSessionLocal() as session:
        owner = User(
            username=f"flow_{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            role="admin",
        )
        session.add(owner)
        await session.flush()

        leave = await _seed_document(
            session, owner_id=owner.id, filename="leave.txt", text=DOC_LEAVE, category="hr"
        )
        expenses = await _seed_document(
            session,
            owner_id=owner.id,
            filename="expenses.txt",
            text=DOC_EXPENSES,
            category="finance",
        )
        doc_ids = [leave.id, expenses.id]

        assert await get_vector_store().count() == leave.chunk_count + expenses.chunk_count

        retriever = HybridRetriever(
            session, embedding_model=_StubEmbeddingModel(384), reranker=_StubReranker()
        )

        dense = await retriever.retrieve(
            "How many days of paid annual leave?", document_ids=doc_ids, top_k=5, mode="dense"
        )
        assert dense
        assert {hit.document_id for hit in dense} <= set(doc_ids)

        bm25_leave = await retriever.retrieve(
            "paid annual leave days", document_ids=doc_ids, top_k=5, mode="bm25"
        )
        assert bm25_leave
        assert bm25_leave[0].document_id == leave.id, "BM25 should rank the leave doc first"
        assert {hit.document_id for hit in bm25_leave} <= set(doc_ids)

        # Access filtering: a caller that may only see expenses gets no leave hits.
        bm25_expenses_only = await retriever.retrieve(
            "annual leave accrues monthly", document_ids=[expenses.id], top_k=5, mode="bm25"
        )
        assert bm25_expenses_only == []

        bm25_leave_only = await retriever.retrieve(
            "annual leave accrues monthly", document_ids=[leave.id], top_k=5, mode="bm25"
        )
        assert bm25_leave_only

        hybrid = await retriever.retrieve(
            "How many days of paid annual leave?", document_ids=doc_ids, top_k=5, mode="hybrid"
        )
        assert hybrid
        # Fusion must surface chunks from both documents (BM25 ranks leave first,
        # dense ranks by the stub vectors), bounded to accessible documents.
        assert {hit.document_id for hit in hybrid} == set(doc_ids)

        category_filtered = await retriever.retrieve(
            "leave policy",
            document_ids=doc_ids,
            extra_filters={"category": "finance"},
            top_k=5,
            mode="hybrid",
        )
        assert category_filtered
        assert all(hit.document_id == expenses.id for hit in category_filtered)


class _StubReranker:
    enabled = False

    async def rerank(self, query, candidates, *, top_n):
        return candidates[:top_n]
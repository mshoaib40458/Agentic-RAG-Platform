"""Unit tests for Phase 3: Database hardening, streaming cleanup, and ingestion resilience."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.constants import DocumentStatus
from app.core.exceptions import UnsupportedMediaTypeError
from app.db.models.document import Document, DocumentChunk
from app.db.models.feedback import Feedback
from app.db.models.query import Query
from app.db.session import build_engine
from app.ingestion.pipeline import DocumentIngestor
from app.llm.embeddings import HuggingFaceEmbeddingModel
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_sqlite_foreign_keys_enforced():
    eng = build_engine("sqlite+aiosqlite:///:memory:")
    async with eng.connect() as conn:
        res = await conn.exec_driver_sql("PRAGMA foreign_keys;")
        fk_enabled = res.fetchone()[0]
        assert fk_enabled == 1
    await eng.dispose()


def test_model_indexes_and_unique_constraints():
    # Verify Document indexes
    doc_index_names = {idx.name for idx in Document.__table__.indexes}
    assert "ix_documents_owner_status" in doc_index_names
    assert "ix_documents_collection_status" in doc_index_names

    # Verify DocumentChunk index
    chunk_index_names = {idx.name for idx in DocumentChunk.__table__.indexes}
    assert "ix_chunks_document_index" in chunk_index_names

    # Verify Query indexes
    query_index_names = {idx.name for idx in Query.__table__.indexes}
    assert "ix_queries_user_created" in query_index_names
    assert "ix_queries_user_status" in query_index_names

    # Verify Feedback unique constraint
    feedback_unique = {c.name for c in Feedback.__table__.constraints}
    assert "uq_feedback_query_user" in feedback_unique


@pytest.mark.asyncio
async def test_upload_streaming_error_cleans_up_orphaned_file(tmp_path, monkeypatch):
    service = DocumentService(session=AsyncMock())
    monkeypatch.setattr(service.settings, "storage_dir", str(tmp_path / "storage"))

    # Create mock upload that fails during read with empty file error
    upload = MagicMock()
    upload.filename = "test.txt"
    upload.content_type = "text/plain"
    upload.read = AsyncMock(return_value=b"")

    owner = MagicMock()
    owner.id = "user1"

    with pytest.raises(UnsupportedMediaTypeError):
        await service.create_document(upload=upload, owner=owner)

    # Check upload_path directory has 0 files left behind
    upload_dir = service.settings.upload_path
    if upload_dir.exists():
        assert len(list(upload_dir.iterdir())) == 0


@pytest.mark.asyncio
async def test_pipeline_vector_cleanup_on_ingestion_failure():
    mock_session = AsyncMock()
    mock_vector_store = AsyncMock()
    mock_embedding = AsyncMock()

    ingestor = DocumentIngestor(
        session=mock_session,
        embedding_model=mock_embedding,
        vector_store=mock_vector_store,
    )

    doc = Document(
        id=str(uuid.uuid4()),
        filename="test.txt",
        file_type=".txt",
        size_bytes=100,
        checksum="abc",
        storage_path="/nonexistent/file.txt",
        owner_id="u1",
        status=DocumentStatus.QUEUED.value,
    )

    await ingestor.run(doc)

    assert doc.status == DocumentStatus.FAILED.value
    # Verify vector store cleanup was called for the failed document
    mock_vector_store.delete_by_document.assert_awaited_with(doc.id)


@pytest.mark.asyncio
async def test_huggingface_embeddings_batching_and_retry():
    settings = MagicMock()
    settings.hf_api_token = "fake-token"
    settings.embedding_dim = 3
    settings.embedding_model = "test-model"
    settings.embedding_batch_size = 2

    hf_model = HuggingFaceEmbeddingModel(settings=settings)

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.raise_for_status = MagicMock()
    mock_resp_200.json.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    responses = [mock_resp_429, mock_resp_200]

    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=responses)) as mock_post:
        vectors = await hf_model.embed_documents(["chunk 1", "chunk 2"])
        assert len(vectors) == 2
        assert mock_post.call_count == 2

"""Unit tests for Phase 2 retrieval, vector store, and metadata synchronization fixes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qdrant_client import QdrantClient, models

from app.agent.nodes import AgentNodes
from app.core.config import Settings
from app.retrieval.bm25 import BM25Retriever, _IndexEntry, _tokenize
from app.retrieval.vector_store import QdrantVectorStore, VectorRecord, _build_filter


def test_build_filter_admin_no_scoping():
    filt = _build_filter(models, document_ids=None, extra_filters=None, tenant_context={"role": "admin", "user_id": "u1"})
    assert filt is None


def test_build_filter_non_admin_tenant_scoping():
    filt = _build_filter(
        models,
        document_ids=None,
        extra_filters={"category": "hr"},
        tenant_context={"role": "user", "user_id": "user123"},
    )
    assert filt is not None
    assert len(filt.must) == 2
    # First condition is the tenant should-filter
    tenant_cond = filt.must[0]
    assert isinstance(tenant_cond, models.Filter)
    assert len(tenant_cond.should) == 2
    assert tenant_cond.should[0].key == "owner_id"
    assert tenant_cond.should[0].match.value == "user123"
    assert tenant_cond.should[1].key == "collection"
    assert tenant_cond.should[1].match.value == "public"

    # Second condition is category
    cat_cond = filt.must[1]
    assert cat_cond.key == "category"
    assert cat_cond.match.value == "hr"


def test_build_filter_explicit_document_ids_precedence():
    filt = _build_filter(
        models,
        document_ids=["doc1", "doc2"],
        extra_filters=None,
        tenant_context={"role": "user", "user_id": "user123"},
    )
    assert filt is not None
    assert len(filt.must) == 1
    assert filt.must[0].key == "document_id"
    assert filt.must[0].match.any == ["doc1", "doc2"]


def test_build_filter_empty_document_ids_guaranteed_none():
    filt = _build_filter(
        models,
        document_ids=[],
        extra_filters=None,
        tenant_context={"role": "user", "user_id": "user123"},
    )
    assert filt is not None
    assert filt.must[0].key == "document_id"
    assert filt.must[0].match.value == "__none__"


@pytest.mark.asyncio
async def test_qdrant_vector_store_payload_update_and_tenant_search(tmp_path):
    coll = f"test_{uuid.uuid4().hex[:8]}"
    settings = Settings(
        vector_store="qdrant_local",
        qdrant_path=str(tmp_path / "qdrant"),
        qdrant_collection=coll,
        embedding_dim=4,
    )
    store = QdrantVectorStore(settings=settings)

    try:
        # Upsert 3 points: doc1 owned by user1 (private), doc2 owned by user2 (private), doc3 owned by user2 (public)
        records = [
            VectorRecord(
                id=str(uuid.uuid4()),
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={"document_id": "doc1", "owner_id": "u1", "collection": "private", "category": "engineering"},
            ),
            VectorRecord(
                id=str(uuid.uuid4()),
                vector=[0.9, 0.1, 0.0, 0.0],
                payload={"document_id": "doc2", "owner_id": "u2", "collection": "private", "category": "finance"},
            ),
            VectorRecord(
                id=str(uuid.uuid4()),
                vector=[0.8, 0.2, 0.0, 0.0],
                payload={"document_id": "doc3", "owner_id": "u2", "collection": "public", "category": "general"},
            ),
        ]
        await store.upsert(records)

        # 1. Tenant search for u1 (non-admin) should find doc1 (owned) and doc3 (public), but NOT doc2 (u2's private doc)
        hits_u1 = await store.search(
            [1.0, 0.0, 0.0, 0.0],
            limit=10,
            tenant_context={"role": "user", "user_id": "u1"},
        )
        hit_docs_u1 = {h.payload["document_id"] for h in hits_u1}
        assert "doc1" in hit_docs_u1
        assert "doc3" in hit_docs_u1
        assert "doc2" not in hit_docs_u1

        # 2. Admin search should see all documents
        hits_admin = await store.search(
            [1.0, 0.0, 0.0, 0.0],
            limit=10,
            tenant_context={"role": "admin", "user_id": "admin"},
        )
        hit_docs_admin = {h.payload["document_id"] for h in hits_admin}
        assert hit_docs_admin == {"doc1", "doc2", "doc3"}

        # 3. Test update_document_metadata: update doc1's category to 'research'
        await store.update_document_metadata("doc1", {"category": "research"})

        hits_updated = await store.search(
            [1.0, 0.0, 0.0, 0.0],
            limit=10,
            extra_filters={"category": "research"},
        )
        assert len(hits_updated) == 1
        assert hits_updated[0].payload["document_id"] == "doc1"
        assert hits_updated[0].payload["category"] == "research"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_bm25_precomputed_tokens_and_tenant_scoping():
    entries = [
        _IndexEntry(
            id="c1",
            text="Annual leave entitlement is twenty days per year.",
            page=1,
            chunk_index=0,
            document_id="doc_leave",
            document_name="leave.txt",
            category="hr",
            collection="private",
            owner_id="u1",
            tokens=frozenset(_tokenize("Annual leave entitlement is twenty days per year.")),
        ),
        _IndexEntry(
            id="c2",
            text="Expense reimbursement requires manager approval for travel.",
            page=1,
            chunk_index=0,
            document_id="doc_expense",
            document_name="expense.txt",
            category="finance",
            collection="private",
            owner_id="u2",
            tokens=frozenset(_tokenize("Expense reimbursement requires manager approval for travel.")),
        ),
        _IndexEntry(
            id="c3",
            text="Company handbook with general code of conduct and leave guidelines.",
            page=1,
            chunk_index=0,
            document_id="doc_handbook",
            document_name="handbook.txt",
            category="general",
            collection="public",
            owner_id="u2",
            tokens=frozenset(_tokenize("Company handbook with general code of conduct and leave guidelines.")),
        ),
    ]

    retriever = BM25Retriever(session=MagicMock())
    from app.retrieval.bm25 import _build
    index = _build(entries)
    retriever._ensure_index = AsyncMock(return_value=index)

    # User u1 searches for "leave":
    # Should match doc_leave (owned by u1) and doc_handbook (public), but if doc_expense had leave, it would be excluded.
    results_u1 = await retriever.retrieve(
        "leave",
        limit=10,
        tenant_context={"role": "user", "user_id": "u1"},
    )
    doc_ids = {r.document_id for r in results_u1}
    assert "doc_leave" in doc_ids
    assert "doc_handbook" in doc_ids

    # If user u1 searches for "expense", doc_expense is private to u2, so results must be empty!
    results_expense = await retriever.retrieve(
        "expense",
        limit=10,
        tenant_context={"role": "user", "user_id": "u1"},
    )
    assert len(results_expense) == 0

    # Admin user searching for "expense" gets doc_expense
    results_admin = await retriever.retrieve(
        "expense",
        limit=10,
        tenant_context={"role": "admin", "user_id": "admin"},
    )
    assert len(results_admin) == 1
    assert results_admin[0].document_id == "doc_expense"


@pytest.mark.asyncio
async def test_agent_nodes_retrieve_passes_tenant_context():
    mock_retriever = AsyncMock()
    mock_retriever.retrieve.return_value = []
    nodes = AgentNodes(retriever=mock_retriever, chat_model=MagicMock(), settings=MagicMock())

    # Case 1: user with accessible documents but no document_ids filter requested
    state = {
        "question": "test question",
        "current_query_index": 0,
        "sub_queries": ["test query"],
        "filters": {},
        "accessible_document_ids": ["doc1", "doc2"],
        "user_id": "u_test",
        "role": "user",
        "iterations": 0,
    }
    await nodes.retrieve(state)
    assert mock_retriever.retrieve.called
    call_kwargs = mock_retriever.retrieve.call_args.kwargs
    assert call_kwargs["document_ids"] is None
    assert call_kwargs["tenant_context"] == {"user_id": "u_test", "role": "user"}

    # Case 2: non-admin user with no accessible documents at all
    mock_retriever.reset_mock()
    state_empty = {
        "question": "test question",
        "current_query_index": 0,
        "sub_queries": ["test query"],
        "filters": {},
        "accessible_document_ids": [],
        "user_id": "u_empty",
        "role": "user",
        "iterations": 0,
    }
    await nodes.retrieve(state_empty)
    call_kwargs_empty = mock_retriever.retrieve.call_args.kwargs
    assert call_kwargs_empty["document_ids"] == []

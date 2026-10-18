"""Unit tests for Phase 4: Observability, evaluation fault tolerance, and context guardrails."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.prompts import render_history
from app.api.v1.health import health
from app.evaluation.dataset import EvalItem
from app.evaluation.runner import evaluate_dataset


@pytest.mark.asyncio
async def test_health_probes_healthy():
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    with patch("app.retrieval.vector_store.get_vector_store") as mock_store:
        mock_store.return_value.count = AsyncMock(return_value=42)
        res = await health(session=mock_session)
        assert res.status == "ok"
        assert res.database == "ok"
        assert res.vector_store == "ok"


@pytest.mark.asyncio
async def test_health_probes_vector_store_degraded():
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    with patch("app.retrieval.vector_store.get_vector_store") as mock_store:
        mock_store.return_value.count = AsyncMock(side_effect=Exception("Qdrant unreachable"))
        res = await health(session=mock_session)
        assert res.status == "degraded"
        assert res.database == "ok"
        assert res.vector_store == "unavailable"


@pytest.mark.asyncio
async def test_health_probes_database_degraded():
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB connection timeout")

    with patch("app.retrieval.vector_store.get_vector_store") as mock_store:
        mock_store.return_value.count = AsyncMock(return_value=10)
        res = await health(session=mock_session)
        assert res.status == "degraded"
        assert res.database == "unavailable"
        assert res.vector_store == "ok"


@pytest.mark.asyncio
async def test_evaluate_dataset_fault_tolerance():
    item1 = EvalItem(
        question="What is the leave policy?",
        relevant_document_ids=["doc1"],
        expected_answer="20 days",
    )
    item2 = EvalItem(
        question="What is the expense limit?",
        relevant_document_ids=["doc2"],
        expected_answer="100 dollars",
    )

    mock_session = AsyncMock()

    # Create mock chunks for successful item
    mock_chunk = MagicMock()
    mock_chunk.id = "c2"
    mock_chunk.document_id = "doc2"

    with patch("app.evaluation.runner.HybridRetriever") as mock_retriever_cls:
        retriever_instance = AsyncMock()
        # item1 fails with an exception, item2 succeeds
        retriever_instance.retrieve.side_effect = [
            Exception("Transient retrieval timeout"),
            [mock_chunk],
        ]
        mock_retriever_cls.return_value = retriever_instance

        results = await evaluate_dataset(
            session=mock_session,
            items=[item1, item2],
            include_answer_metrics=False,
        )

        assert results["evaluated_items"] == 1
        assert results["failed_items"] == 1
        assert len(results["per_item"]) == 1
        assert results["per_item"][0]["question"] == "What is the expense limit?"


def test_render_history_truncates_long_answers():
    long_answer = "A" * 2500
    history = [
        {"question": "Tell me everything about the platform.", "answer": long_answer},
        {"question": "Summarize that in one word.", "answer": "Fast."},
    ]

    rendered = render_history(history, max_chars_per_turn=500)
    assert "... [truncated]" in rendered
    # Ensure first turn is bounded
    assert len(rendered) < 1000
    assert "Summarize that in one word." in rendered
    assert "Assistant: Fast." in rendered

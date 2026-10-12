"""Reciprocal Rank Fusion ordering (SRS FR-019)."""

from __future__ import annotations

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.types import RetrievedChunk


def _chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id, text="t", score=score, document_id="d", document_name="f.pdf"
    )


def test_agreement_across_retrievers_ranks_first():
    dense = [_chunk("x", 0.9), _chunk("y", 0.5)]
    keyword = [_chunk("y", 12.0), _chunk("z", 5.0)]
    fused = reciprocal_rank_fusion([dense, keyword], k=60)
    ids = [chunk.id for chunk in fused]
    # "y" is rank 2 in dense but rank 1 in keyword -> highest fused score.
    assert ids[0] == "y"
    assert set(ids) == {"x", "y", "z"}


def test_fusion_marks_source_and_preserves_no_duplicates():
    fused = reciprocal_rank_fusion([[_chunk("a", 1)], [_chunk("a", 1)]], k=60)
    assert len(fused) == 1
    assert fused[0].source == "fused"
    assert fused[0].score > 0


def test_empty_input_returns_empty():
    assert reciprocal_rank_fusion([[], []]) == []

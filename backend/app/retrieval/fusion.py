"""Reciprocal Rank Fusion for combining retriever result lists (SRS FR-019).

RRF is rank-based, so it requires no score normalization between retriever
families (dense cosine similarity vs. BM25). ``k`` (default 60) damps the
influence of top ranks.
"""

from __future__ import annotations

from dataclasses import replace

from app.retrieval.types import RetrievedChunk


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]], *, k: int = 60
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    by_id: dict[str, RetrievedChunk] = {}
    quality: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
            by_id.setdefault(chunk.id, chunk)
            if chunk.quality_score is not None:
                quality[chunk.id] = max(quality.get(chunk.id, 0.0), float(chunk.quality_score))

    fused = [
        replace(by_id[chunk_id], score=score, source="fused", quality_score=quality.get(chunk_id))
        for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]
    return fused

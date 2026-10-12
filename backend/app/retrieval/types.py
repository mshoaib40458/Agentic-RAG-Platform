"""Shared retrieval data structures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RetrievedChunk:
    """A passage returned by any retrieval stage, citation-ready."""

    id: str
    text: str
    score: float
    document_id: str
    document_name: str
    page: int | None = None
    chunk_index: int | None = None
    source: str = "unknown"  # dense | bm25 | fused | rerank
    # Calibrated relevance signal (dense cosine) preserved through fusion and
    # reranking so sufficiency gating stays on a well-defined scale.
    quality_score: float | None = None

    def snippet(self, max_chars: int = 320) -> str:
        text = " ".join(self.text.split())
        return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "\u2026"

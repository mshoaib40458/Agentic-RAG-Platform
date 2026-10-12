"""Reranking providers (SRS FR-022).

A cross-encoder reranker re-scores the fused candidate list against the query
before final context construction. When reranking is disabled (or the model
cannot be loaded) a :class:`NoOpReranker` preserves fusion ordering so the
pipeline degrades gracefully.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.llm.base import RerankCandidate

logger = logging.getLogger(__name__)


class NoOpReranker:
    """Pass-through reranker used when reranking is disabled."""

    @property
    def enabled(self) -> bool:
        return False

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]:
        ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
        return ordered[:top_n]


class CrossEncoderReranker:
    """Cross-encoder reranker backed by Sentence-Transformers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None

    @property
    def enabled(self) -> bool:
        return True

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("loading_reranker_model", extra={"model": self._settings.reranker_model})
            self._model = CrossEncoder(self._settings.reranker_model, device="cpu")
        return self._model

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]:
        if not candidates:
            return []
        model = await asyncio.to_thread(self._load)
        pairs = [(query, candidate.text) for candidate in candidates]
        scores = await asyncio.to_thread(model.predict, pairs)
        rescored = [
            RerankCandidate(id=candidate.id, text=candidate.text, score=float(score))
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        rescored.sort(key=lambda c: c.score, reverse=True)
        return rescored[:top_n]


@lru_cache
def get_reranker():
    """Return the configured reranker, falling back to no-op if unavailable."""
    settings = get_settings()
    if not settings.reranker_enabled:
        return NoOpReranker()
    try:
        return CrossEncoderReranker(settings)
    except Exception:  # pragma: no cover - defensive; import errors surface later
        logger.warning("reranker_init_failed_falling_back_to_noop")
        return NoOpReranker()

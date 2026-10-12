"""Hybrid retrieval orchestration (SRS 4.3 / 8.4).

Combines dense and BM25 candidates, fuses them with RRF, then optionally
reranks. Also exposes the simpler modes used for baseline comparison in
evaluation: ``dense``, ``bm25``, ``hybrid`` (fusion only) and ``hybrid_rerank``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.llm.base import RerankCandidate
from app.llm.reranker import get_reranker
from app.retrieval.bm25 import BM25Retriever
from app.retrieval.dense import DenseRetriever
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

RetrievalMode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]


class HybridRetriever:
    def __init__(
        self,
        session: AsyncSession,
        *,
        embedding_model=None,
        vector_store=None,
        reranker=None,
    ) -> None:
        self.settings = get_settings()
        self.dense = DenseRetriever(embedding_model=embedding_model, vector_store=vector_store)
        self.bm25 = BM25Retriever(session)
        self.reranker = reranker if reranker is not None else get_reranker()

    async def retrieve(
        self,
        query: str,
        *,
        document_ids: list[str] | None,
        extra_filters: dict[str, str] | None = None,
        top_k: int | None = None,
        candidate_k: int | None = None,
        mode: RetrievalMode = "hybrid_rerank",
    ) -> list[RetrievedChunk]:
        top_k = top_k or self.settings.retrieval_top_k
        candidate_k = candidate_k or self.settings.retrieval_candidate_k

        if mode == "dense":
            return await self.dense.retrieve(
                query, limit=top_k, document_ids=document_ids, extra_filters=extra_filters
            )
        if mode == "bm25":
            return await self.bm25.retrieve(
                query, limit=top_k, document_ids=document_ids, extra_filters=extra_filters
            )

        dense_hits, bm25_hits = await asyncio.gather(
            self.dense.retrieve(
                query, limit=candidate_k, document_ids=document_ids, extra_filters=extra_filters
            ),
            self.bm25.retrieve(
                query, limit=candidate_k, document_ids=document_ids, extra_filters=extra_filters
            ),
        )
        fused = reciprocal_rank_fusion([dense_hits, bm25_hits], k=self.settings.rrf_k)

        if mode == "hybrid" or not self.reranker.enabled:
            return fused[:top_k]

        return await self._rerank(query, fused, top_k=top_k, candidate_k=candidate_k)

    async def _rerank(
        self, query: str, fused: list[RetrievedChunk], *, top_k: int, candidate_k: int
    ) -> list[RetrievedChunk]:
        if not fused:
            return []
        pool = fused[: max(candidate_k, top_k)]
        candidates = [
            RerankCandidate(id=chunk.id, text=chunk.text, score=chunk.score) for chunk in pool
        ]
        reranked = await self.reranker.rerank(query, candidates, top_n=top_k)
        by_id = {chunk.id: chunk for chunk in pool}
        return [
            replace(by_id[item.id], score=item.score, source="rerank")
            for item in reranked
            if item.id in by_id
        ]

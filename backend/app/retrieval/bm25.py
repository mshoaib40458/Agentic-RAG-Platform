"""BM25 keyword retrieval (SRS FR-018).

Builds an in-process BM25 index over every indexed chunk. The index is cached
and invalidated whenever the corpus changes (see :func:`invalidate`). Access
control is applied at *result* time by filtering to the caller's authorized
document ids, so the shared index never widens visibility.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DocumentStatus
from app.db.models.document import Document, DocumentChunk
from app.retrieval.types import RetrievedChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(slots=True)
class _IndexEntry:
    id: str
    text: str
    page: int | None
    chunk_index: int | None
    document_id: str
    document_name: str
    category: str | None
    collection: str


class _BM25Index:
    def __init__(self, entries: list[_IndexEntry]) -> None:
        from rank_bm25 import BM25Okapi

        self.entries = entries
        self._bm25 = BM25Okapi([_tokenize(entry.text) for entry in entries])

    def scores(self, query: str) -> list[float]:
        return self._bm25.get_scores(_tokenize(query)).tolist()


_index: _BM25Index | None = None
_lock = asyncio.Lock()


def invalidate() -> None:
    """Drop the cached index; the next query rebuilds it."""
    global _index
    _index = None


def _build(entries: list[_IndexEntry]) -> _BM25Index:
    return _BM25Index(entries)


class BM25Retriever:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_entries(self) -> list[_IndexEntry]:
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.text,
                DocumentChunk.page,
                DocumentChunk.chunk_index,
                Document.id,
                Document.filename,
                Document.category,
                Document.collection,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == DocumentStatus.INDEXED.value)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            _IndexEntry(
                id=row[0],
                text=row[1],
                page=row[2],
                chunk_index=row[3],
                document_id=row[4],
                document_name=row[5],
                category=row[6],
                collection=row[7],
            )
            for row in rows
        ]

    async def _ensure_index(self) -> _BM25Index | None:
        global _index
        if _index is not None:
            return _index
        async with _lock:
            if _index is not None:
                return _index
            entries = await self._load_entries()
            if not entries:
                return None
            _index = await asyncio.to_thread(_build, entries)
            return _index

    async def retrieve(
        self,
        query: str,
        *,
        limit: int,
        document_ids: list[str] | None = None,
        extra_filters: dict[str, str] | None = None,
    ) -> list[RetrievedChunk]:
        if document_ids is not None and not document_ids:
            return []
        index = await self._ensure_index()
        if index is None:
            return []

        allowed_docs = set(document_ids) if document_ids is not None else None
        query_tokens = set(_tokenize(query))
        scores = index.scores(query)
        ranked = sorted(range(len(index.entries)), key=lambda i: scores[i], reverse=True)

        results: list[RetrievedChunk] = []
        for position in ranked:
            entry = index.entries[position]
            # BM25Okapi can produce negative (or zero) scores when query terms
            # occur in nearly every document; a score <= 0 does not mean the
            # passage is irrelevant. Inclusion is decided by token overlap, and
            # the (possibly negative) score only orders the overlapping results.
            if not (query_tokens & set(_tokenize(entry.text))):
                continue
            if allowed_docs is not None and entry.document_id not in allowed_docs:
                continue
            if extra_filters:
                if "category" in extra_filters and entry.category != extra_filters["category"]:
                    continue
                if (
                    "collection" in extra_filters
                    and entry.collection != extra_filters["collection"]
                ):
                    continue
            results.append(
                RetrievedChunk(
                    id=entry.id,
                    text=entry.text,
                    score=float(scores[position]),
                    document_id=entry.document_id,
                    document_name=entry.document_name,
                    page=entry.page,
                    chunk_index=entry.chunk_index,
                    source="bm25",
                )
            )
            if len(results) >= limit:
                break
        return results

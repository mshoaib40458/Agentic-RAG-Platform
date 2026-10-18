"""Vector store abstraction backed by Qdrant.

Qdrant is used in one of two modes, selected by ``VECTOR_STORE``:

* ``qdrant_local`` - embedded, file-backed instance (zero external services).
* ``qdrant``       - a Qdrant server reached over HTTP.

The client is synchronous, so every operation is dispatched to a worker thread
to keep the async event loop responsive. Payloads carry the metadata required
for citation and access filtering (SRS FR-023/FR-027).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.exceptions import RetrievalError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VectorRecord:
    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SearchHit:
    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return str(self.payload.get("text", ""))


class VectorStore(Protocol):
    async def upsert(self, records: list[VectorRecord]) -> None: ...
    async def search(
        self,
        vector: list[float],
        *,
        limit: int,
        document_ids: list[str] | None = None,
        extra_filters: dict[str, str] | None = None,
        tenant_context: dict[str, str] | None = None,
    ) -> list[SearchHit]: ...
    async def update_document_metadata(self, document_id: str, metadata: dict[str, Any]) -> None: ...
    async def delete_by_document(self, document_id: str) -> None: ...
    async def delete_ids(self, ids: list[str]) -> None: ...
    async def count(self) -> int: ...


def _build_filter(
    models: Any,
    document_ids: list[str] | None,
    extra_filters: dict[str, str] | None,
    tenant_context: dict[str, str] | None = None,
) -> Any | None:
    must: list[Any] = []
    if document_ids is not None:
        if not document_ids:
            # No accessible documents -> guaranteed-empty match.
            return models.Filter(must=[models.FieldCondition(
                key="document_id", match=models.MatchValue(value="__none__")
            )])
        must.append(
            models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))
        )
    elif tenant_context is not None:
        role = tenant_context.get("role")
        user_id = tenant_context.get("user_id")
        if role != "admin" and user_id:
            # Non-admin tenant isolation: user can only see their own documents OR public collection
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(key="owner_id", match=models.MatchValue(value=user_id)),
                        models.FieldCondition(key="collection", match=models.MatchValue(value="public")),
                    ]
                )
            )
    for key, value in (extra_filters or {}).items():
        must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
    return models.Filter(must=must) if must else None


class QdrantVectorStore:
    def __init__(self, settings: Settings | None = None) -> None:
        try:
            from qdrant_client import QdrantClient, models
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RetrievalError(
                "The 'qdrant-client' package is not installed.", code="vector_store_unavailable"
            ) from exc

        self._settings = settings or get_settings()
        self._models = models
        self._dimension = self._settings.embedding_dim
        self._collection = self._settings.qdrant_collection
        if self._settings.vector_store == "qdrant_local":
            Path(self._settings.qdrant_path).resolve().mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=self._settings.qdrant_path)
        else:
            self._client = QdrantClient(
                url=self._settings.qdrant_url, api_key=self._settings.qdrant_api_key or None
            )
        self._ensure_collection()

    def _ensure_payload_indexes(self) -> None:
        """Create keyword payload indexes on frequently filtered fields."""
        indexed_fields = ("document_id", "owner_id", "collection", "category")
        for field_name in indexed_fields:
            try:
                self._client.create_payload_index(
                    collection_name=self._collection,
                    field_name=field_name,
                    field_schema=self._models.PayloadSchemaType.KEYWORD,
                )
            except Exception:  # noqa: BLE001 - indexing is best-effort (e.g. local Qdrant ignores)
                pass

    def _ensure_collection(self) -> None:
        models = self._models
        if self._client.collection_exists(self._collection):
            self._verify_dimension()
            self._ensure_payload_indexes()
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=models.VectorParams(
                size=self._dimension, distance=models.Distance.COSINE
            ),
        )
        logger.info("created_vector_collection", extra={"collection": self._collection})
        self._ensure_payload_indexes()

    def _verify_dimension(self) -> None:
        """Fail fast when the collection was built for a different embedding model.

        Mixing vectors of different sizes silently corrupts retrieval, so we
        surface a clear operator error instead (SRS NFR-006).
        """
        try:
            info = self._client.get_collection(self._collection)
            params = info.config.params.vectors
            # Named-vector configs expose a mapping; only guard single-vector ones.
            size = getattr(params, "size", None) if not isinstance(params, dict) else None
            if size is not None and int(size) != int(self._dimension):
                raise RetrievalError(
                    f"Collection '{self._collection}' has dimension {size} but the "
                    f"configured embedding model produces {self._dimension}. Re-ingest "
                    "into a fresh collection or update EMBEDDING_DIM.",
                    code="embedding_dimension_mismatch",
                )
        except RetrievalError:
            raise
        except Exception:  # noqa: BLE001 - introspection is best-effort
            logger.warning("vector_dimension_check_skipped", exc_info=True)

    async def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        models = self._models
        points = [
            models.PointStruct(id=record.id, vector=record.vector, payload=record.payload)
            for record in records
        ]
        try:
            await asyncio.to_thread(
                self._client.upsert, collection_name=self._collection, points=points, wait=True
            )
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise RetrievalError("Failed to write vectors to the store.") from exc

    async def search(
        self,
        vector: list[float],
        *,
        limit: int,
        document_ids: list[str] | None = None,
        extra_filters: dict[str, str] | None = None,
        tenant_context: dict[str, str] | None = None,
    ) -> list[SearchHit]:
        if document_ids is not None and not document_ids:
            return []
        query_filter = _build_filter(
            self._models, document_ids, extra_filters, tenant_context=tenant_context
        )
        try:
            results = await asyncio.to_thread(
                self._query,
                vector,
                limit=limit,
                query_filter=query_filter,
            )
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise RetrievalError("Vector search failed.") from exc
        return [
            SearchHit(id=str(point.id), score=float(point.score), payload=point.payload or {})
            for point in results
        ]

    async def update_document_metadata(self, document_id: str, metadata: dict[str, Any]) -> None:
        """Update payload metadata across all chunks belonging to a document."""
        if not metadata:
            return
        models = self._models
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    )
                ]
            )
        )
        try:
            await asyncio.to_thread(
                self._client.set_payload,
                collection_name=self._collection,
                payload=metadata,
                points=selector,
                wait=True,
            )
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise RetrievalError("Failed to update vector payload metadata.") from exc

    def _query(self, vector: list[float], *, limit: int, query_filter: Any) -> list[Any]:
        # ``search`` was removed in qdrant-client >= 1.16 in favour of
        # ``query_points``; support both so pinned older clients keep working.
        query_points = getattr(self._client, "query_points", None)
        if query_points is not None:
            response = query_points(
                collection_name=self._collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
            return list(response.points)
        legacy_search = getattr(self._client, "search", None)
        if legacy_search is not None:
            return list(
                legacy_search(
                    collection_name=self._collection,
                    query_vector=vector,
                    limit=limit,
                    query_filter=query_filter,
                    with_payload=True,
                )
            )
        raise RetrievalError("The installed qdrant-client exposes no search method.")

    async def delete_by_document(self, document_id: str) -> None:
        models = self._models
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    )
                ]
            )
        )
        await asyncio.to_thread(
            self._client.delete,
            collection_name=self._collection,
            points_selector=selector,
            wait=True,
        )

    async def delete_ids(self, ids: list[str]) -> None:
        if not ids:
            return
        await asyncio.to_thread(
            self._client.delete,
            collection_name=self._collection,
            points_selector=self._models.PointIdsList(points=ids),
            wait=True,
        )

    async def count(self) -> int:
        result = await asyncio.to_thread(
            self._client.count, collection_name=self._collection, exact=True
        )
        return int(result.count)

    def close(self) -> None:
        """Release the underlying client (avoids noisy teardown)."""
        with contextlib.suppress(Exception):  # noqa: BLE001 - best effort on shutdown
            self._client.close()


_store: QdrantVectorStore | None = None


def get_vector_store() -> QdrantVectorStore:
    """Process-wide cached vector store instance."""
    global _store
    if _store is None:
        _store = QdrantVectorStore()
    return _store


def reset_vector_store() -> None:
    """Clear the cached store (used by tests)."""
    global _store
    _store = None

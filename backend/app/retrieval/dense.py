"""Dense (semantic) retrieval via embeddings + vector store (SRS FR-017)."""

from __future__ import annotations

from app.llm.embeddings import get_embedding_model
from app.retrieval.types import RetrievedChunk
from app.retrieval.vector_store import get_vector_store


class DenseRetriever:
    def __init__(self, *, embedding_model=None, vector_store=None) -> None:
        self.embedding_model = embedding_model or get_embedding_model()
        self.vector_store = vector_store or get_vector_store()

    async def retrieve(
        self,
        query: str,
        *,
        limit: int,
        document_ids: list[str] | None = None,
        extra_filters: dict[str, str] | None = None,
    ) -> list[RetrievedChunk]:
        vector = await self.embedding_model.embed_query(query)
        hits = await self.vector_store.search(
            vector, limit=limit, document_ids=document_ids, extra_filters=extra_filters
        )
        return [
            RetrievedChunk(
                # The vector-store point id is a canonical UUID; the payload
                # chunk_id is the database id that BM25 and fusion key on.
                id=str(hit.payload.get("chunk_id") or hit.id),
                text=hit.text,
                score=hit.score,
                document_id=str(hit.payload.get("document_id", "")),
                document_name=str(hit.payload.get("filename", "")),
                page=hit.payload.get("page"),
                chunk_index=hit.payload.get("chunk_index"),
                source="dense",
                quality_score=hit.score,
            )
            for hit in hits
        ]

"""Embedding providers.

Two implementations are provided behind the :class:`EmbeddingModel` protocol:

* :class:`LocalEmbeddingModel` - runs a Sentence-Transformers model in-process
  (default; no external calls). The heavy model is loaded lazily on first use and
  inference is dispatched to a worker thread to avoid blocking the event loop.
* :class:`HuggingFaceEmbeddingModel` - calls the Hugging Face Inference API.

Select the provider with ``EMBEDDING_PROVIDER``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)

_HF_INFERENCE_BASE = "https://api-inference.huggingface.co/models"


class LocalEmbeddingModel:
    """Sentence-Transformers embeddings executed in a worker thread."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None  # loaded lazily
        self._load_lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dim

    def _load(self):
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as exc:  # pragma: no cover - optional dependency path
                        raise ProviderError(
                            "sentence-transformers is not installed; install the local-ml extra "
                            "or set EMBEDDING_PROVIDER=huggingface.",
                            code="embeddings_unavailable",
                        ) from exc
                    logger.info(
                        "loading_embedding_model", extra={"model": self._settings.embedding_model}
                    )
                    self._model = SentenceTransformer(
                        self._settings.embedding_model, device="cpu"
                    )
        return self._model

    async def warmup(self) -> None:
        """Eagerly load the model so the first real query is not penalised."""
        await asyncio.to_thread(self._load)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = await asyncio.to_thread(self._load)
        vectors = await asyncio.to_thread(
            model.encode,
            texts,
            batch_size=self._settings.embedding_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [vector.tolist() for vector in vectors]

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]


class HuggingFaceEmbeddingModel:
    """Embeddings via the Hugging Face Inference API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.hf_api_token:
            raise ProviderError(
                "HF_API_TOKEN is required for the huggingface embedding provider.",
                code="hf_token_missing",
            )

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dim

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        url = f"{_HF_INFERENCE_BASE}/{self._settings.embedding_model}"
        headers = {"Authorization": f"Bearer {self._settings.hf_api_token}"}
        batch_size = max(1, self._settings.embedding_batch_size)
        results: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                payload = {"inputs": batch, "options": {"wait_for_model": True}}
                data = None
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.post(url, headers=headers, json=payload)
                        if (
                            response.status_code in {429, 503, 504}
                            and attempt < max_retries - 1
                        ):
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        response.raise_for_status()
                        data = response.json()
                        break
                    except httpx.HTTPError as exc:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        raise ProviderError(
                            "Hugging Face inference request failed.", code="embeddings_failed"
                        ) from exc

                # The API returns a list of vectors for a batched input.
                if data and isinstance(data[0], (int, float)):
                    results.append(data)
                elif data:
                    results.extend(data)
        return results

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]


@lru_cache
def get_embedding_model():
    settings = get_settings()
    if settings.embedding_provider == "huggingface":
        return HuggingFaceEmbeddingModel(settings)
    return LocalEmbeddingModel(settings)

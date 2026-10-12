"""Provider-agnostic protocols for LLM, embedding, and reranking components.

Concrete implementations live alongside these protocols. Application code
depends only on the protocols so providers can be swapped via configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


@dataclass(slots=True)
class ChatResult:
    """Normalized result of a chat completion call."""

    content: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ChatModel(Protocol):
    """A chat-completion capable language model."""

    @property
    def model_name(self) -> str: ...

    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult: ...


@runtime_checkable
class EmbeddingModel(Protocol):
    """Maps text to dense vectors for semantic retrieval."""

    @property
    def dimension(self) -> int: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


@dataclass(slots=True)
class RerankCandidate:
    """A passage presented to the reranker."""

    id: str
    text: str
    score: float = 0.0


@runtime_checkable
class Reranker(Protocol):
    """Re-scores candidate passages conditioned on the query (SRS FR-022)."""

    @property
    def enabled(self) -> bool: ...

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], *, top_n: int
    ) -> list[RerankCandidate]: ...

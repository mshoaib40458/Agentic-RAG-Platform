"""Query and answer schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import QueryStatus, VerificationStatus
from app.schemas.common import ORMModel


class QueryFilters(BaseModel):
    """Optional metadata narrowing applied to retrieval (SRS FR-020/FR-027)."""

    document_ids: list[str] | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=128)
    collection: str | None = Field(default=None, max_length=128)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    filters: QueryFilters | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    stream: bool = False
    conversation_id: str | None = Field(default=None, max_length=32)


class Citation(BaseModel):
    """A traceable pointer back to source evidence (SRS FR-036/FR-037)."""

    document_id: str
    document_name: str
    chunk_id: str
    page: int | None = None
    snippet: str
    score: float = 0.0


class EvidenceItem(Citation):
    """A retrieved passage, with the score used for ranking."""


class AnswerRead(ORMModel):
    id: str
    content: str
    model: str
    verification_status: VerificationStatus
    citations: list[Citation] = Field(default_factory=list)
    used_evidence: list[EvidenceItem] = Field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class QueryRead(ORMModel):
    id: str
    question: str
    filters: dict[str, Any] = Field(default_factory=dict)
    status: QueryStatus
    intent: str | None = None
    latency_ms: int | None = None
    stage_timings: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    answer: AnswerRead | None = None
    created_at: datetime
    conversation_id: str | None = None


class QueryAnalytics(BaseModel):
    """Aggregated query latency/quality signals (SRS 8.3)."""

    total_queries: int
    latency_samples: int
    avg_latency_ms: int | None = None
    p50_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    abstention_count: int = 0
    abstention_rate: float = 0.0
    verification_breakdown: dict[str, int] = Field(default_factory=dict)
    intent_breakdown: dict[str, int] = Field(default_factory=dict)
    answer: AnswerRead | None = None


class QueryStatusRead(ORMModel):
    id: str
    status: QueryStatus
    error_message: str | None = None
    latency_ms: int | None = None

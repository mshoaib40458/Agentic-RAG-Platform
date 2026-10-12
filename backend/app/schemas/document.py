"""Document schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import DocumentStatus
from app.schemas.common import ORMModel


class DocumentRead(ORMModel):
    id: str
    filename: str
    file_type: str
    content_type: str | None = None
    size_bytes: int
    owner_id: str
    collection: str
    category: str | None = None
    status: DocumentStatus
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    """Mutable document metadata (SRS FR-014)."""

    category: str | None = Field(default=None, max_length=128)
    collection: str | None = Field(default=None, max_length=128)


class DocumentStats(BaseModel):
    total: int
    indexed: int
    processing: int
    queued: int
    failed: int
    total_chunks: int

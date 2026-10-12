"""Feedback and evaluation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import EvaluationStatus
from app.schemas.common import ORMModel


class FeedbackCreate(BaseModel):
    query_id: str
    rating: int = Field(description="+1 for helpful, -1 for not helpful")
    comment: str | None = Field(default=None, max_length=2000)

    def model_post_init(self, __context: object) -> None:
        if self.rating not in (-1, 1):
            raise ValueError("rating must be +1 or -1")


class FeedbackRead(ORMModel):
    id: str
    query_id: str
    user_id: str
    rating: int
    comment: str | None = None
    created_at: datetime


class EvaluationCreate(BaseModel):
    dataset_version: str = Field(min_length=1, max_length=64)
    dataset_path: str | None = None
    config: dict = Field(default_factory=dict)


class EvaluationRead(ORMModel):
    id: str
    dataset_version: str
    dataset_path: str
    config: dict
    status: EvaluationStatus
    metrics: dict
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

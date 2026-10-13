"""Conversation schemas for multi-turn chat."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.query import QueryRead


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationRead(ORMModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    turn_count: int = 0


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    turns: list[QueryRead] = Field(default_factory=list)

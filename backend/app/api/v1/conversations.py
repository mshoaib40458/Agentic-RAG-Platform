"""Conversation endpoints for multi-turn chat."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import PaginationDep, SessionDep, require_permission
from app.core.constants import Permission
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.schemas.common import Page
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
)
from app.schemas.query import QueryRead
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])

ChatDep = Annotated[User, Depends(require_permission(Permission.QUERY))]


def _to_detail(conversation: Conversation) -> ConversationDetail:
    turns: list[QueryRead] = []
    for turn in conversation.turns:
        query = turn.query
        if query is None:
            continue
        read = QueryRead.model_validate(query)
        read.conversation_id = conversation.id
        turns.append(read)
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        turns=turns,
    )


@router.get("", response_model=Page[ConversationRead])
async def list_conversations(
    session: SessionDep, user: ChatDep, pagination: PaginationDep
) -> Page[ConversationRead]:
    rows, total = await ConversationService(session).list_conversations(
        user=user, limit=pagination.limit, offset=pagination.offset
    )
    items = [
        ConversationRead.model_validate(conversation, from_attributes=True).model_copy(
            update={"turn_count": count}
        )
        for conversation, count in rows
    ]
    return Page(
        items=items, total=total, limit=pagination.limit, offset=pagination.offset
    )


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate, session: SessionDep, user: ChatDep
) -> ConversationRead:
    conversation = await ConversationService(session).create(user=user, title=payload.title)
    return ConversationRead.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, session: SessionDep, user: ChatDep
) -> ConversationDetail:
    conversation = await ConversationService(session).get(conversation_id, user=user)
    return _to_detail(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str, session: SessionDep, user: ChatDep
) -> Response:
    await ConversationService(session).delete(conversation_id, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

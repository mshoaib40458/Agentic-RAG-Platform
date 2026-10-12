"""Question-answering endpoints (SRS 4.4/4.5 / 5.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import PaginationDep, SessionDep, require_permission
from app.core.constants import Permission
from app.db.models.user import User
from app.schemas.common import Page
from app.schemas.query import QueryRead, QueryRequest, QueryStatusRead
from app.services.query_service import QueryService

router = APIRouter(prefix="/query", tags=["query"])

QueryDep = Annotated[User, Depends(require_permission(Permission.QUERY))]


@router.post("", response_model=QueryRead)
async def submit_query(payload: QueryRequest, session: SessionDep, user: QueryDep) -> QueryRead:
    query = await QueryService(session).run(user=user, request=payload)
    return QueryRead.model_validate(query)


@router.get("", response_model=Page[QueryRead])
async def list_queries(
    session: SessionDep, user: QueryDep, pagination: PaginationDep
) -> Page[QueryRead]:
    queries, total = await QueryService(session).list_queries(
        user=user, limit=pagination.limit, offset=pagination.offset
    )
    return Page(
        items=[QueryRead.model_validate(query) for query in queries],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{query_id}", response_model=QueryRead)
async def get_query(query_id: str, session: SessionDep, user: QueryDep) -> QueryRead:
    query = await QueryService(session).get_query(query_id, user=user)
    return QueryRead.model_validate(query)


@router.get("/{query_id}/status", response_model=QueryStatusRead)
async def get_query_status(query_id: str, session: SessionDep, user: QueryDep) -> QueryStatusRead:
    query = await QueryService(session).get_query(query_id, user=user)
    return QueryStatusRead.model_validate(query)

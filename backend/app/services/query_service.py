"""Query orchestration: persistence + agent execution (SRS 4.4/4.5)."""

from __future__ import annotations

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import AgentRunner
from app.core.config import get_settings
from app.core.constants import QueryStatus, UserRole
from app.core.exceptions import AppError, NotFoundError
from app.db.models.query import Answer, Query
from app.db.models.user import User
from app.llm.groq_client import get_chat_model
from app.repositories.document_repo import DocumentRepository
from app.repositories.query_repo import QueryRepository
from app.retrieval.hybrid import HybridRetriever
from app.schemas.query import QueryRequest
from app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.queries = QueryRepository(session)
        self.documents = DocumentRepository(session)
        self.conversations = ConversationService(session)

    async def run(self, *, user: User, request: QueryRequest) -> tuple[Query, str]:
        filters = request.filters.model_dump(exclude_none=True) if request.filters else {}

        conversation = await self.conversations.resolve(
            user=user, conversation_id=request.conversation_id, question=request.question
        )
        history = await self.conversations.history_for(
            conversation, limit=self.settings.agent_history_turns
        )

        query = Query(
            user_id=user.id,
            question=request.question,
            filters=filters,
            status=QueryStatus.PROCESSING.value,
        )
        await self.queries.add(query)

        started = time.perf_counter()
        try:
            accessible = await self.documents.accessible_document_ids(
                user_id=user.id, role=user.role
            )
            runner = AgentRunner(
                retriever=HybridRetriever(self.session),
                chat_model=get_chat_model(),
                settings=self.settings,
            )
            result = await runner.run(
                question=request.question,
                user_id=user.id,
                role=user.role,
                accessible_document_ids=accessible,
                history=history,
                filters=filters,
                top_k=request.top_k,
            )
        except AppError as exc:
            query.status = QueryStatus.FAILED.value
            query.error_message = exc.message
            query.latency_ms = int((time.perf_counter() - started) * 1000)
            await self.session.commit()
            logger.warning("query_failed", extra={"query_id": query.id, "code": exc.code})
            raise AppError(
                exc.message, code=exc.code, details={"query_id": query.id}
            ) from exc
        except Exception:
            query.status = QueryStatus.FAILED.value
            query.error_message = "Unexpected error while processing the query."
            query.latency_ms = int((time.perf_counter() - started) * 1000)
            await self.session.commit()
            logger.exception("query_unexpected_error", extra={"query_id": query.id})
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        answer = Answer(
            query_id=query.id,
            content=result.answer,
            model=result.model or self.settings.groq_model,
            verification_status=result.verification_status,
            citations=result.citations,
            used_evidence=result.used_evidence,
            prompt_tokens=result.usage.get("prompt_tokens"),
            completion_tokens=result.usage.get("completion_tokens"),
        )
        self.session.add(answer)
        query.status = QueryStatus.COMPLETED.value
        query.intent = result.intent or None
        query.latency_ms = latency_ms
        query.stage_timings = {**result.stage_timings, "total_ms": latency_ms}
        query.error_message = None
        await self.session.flush()

        await self.conversations.attach_turn(conversation, query)

        loaded = await self.queries.get_with_answer(query.id)
        return (loaded or query), conversation.id

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def get_query(self, query_id: str, *, user: User) -> Query:
        query = await self.queries.get_with_answer(query_id)
        if query is None:
            raise NotFoundError("Query not found.")
        can_view_all = user.role in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
        if query.user_id != user.id and not can_view_all:
            raise NotFoundError("Query not found.")
        return query

    async def list_queries(
        self, *, user: User, limit: int = 50, offset: int = 0
    ) -> tuple[list[Query], int]:
        include_all = user.role in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
        return await self.queries.list_for_user(
            user_id=user.id, limit=limit, offset=offset, include_all=include_all
        )

    async def analytics(self, *, user: User) -> dict:
        include_all = user.role in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}
        return await self.queries.analytics(user_id=user.id, include_all=include_all)

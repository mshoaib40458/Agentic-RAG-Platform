"""Query and Answer repositories."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.query import Answer, Query
from app.repositories.base import BaseRepository


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((percentile / 100) * (len(ordered) - 1))))
    return ordered[index]


def prune_document_references(
    items: list[dict], document_id: str
) -> list[dict]:
    """Return ``items`` without any entry belonging to ``document_id``.

    ``used_evidence`` holds full passage text and ``citations`` holds snippets;
    both are pruned when a document is deleted so its content is not retained
    in answer history.
    """
    return [item for item in items if item.get("document_id") != document_id]


class QueryRepository(BaseRepository[Query]):
    model = Query

    async def get_with_answer(self, query_id: str) -> Query | None:
        stmt = (
            select(Query)
            .where(Query.id == query_id)
            .options(selectinload(Query.answer))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self, *, user_id: str, limit: int = 50, offset: int = 0, include_all: bool = False
    ) -> tuple[list[Query], int]:
        stmt = select(Query).options(selectinload(Query.answer)).order_by(Query.created_at.desc())
        count_stmt = select(func.count()).select_from(Query)
        if not include_all:
            stmt = stmt.where(Query.user_id == user_id)
            count_stmt = count_stmt.where(Query.user_id == user_id)
        stmt = stmt.limit(limit).offset(offset)
        rows = list((await self.session.execute(stmt)).scalars().all())
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return rows, total

    async def analytics(
        self, *, user_id: str, include_all: bool = False, sample_limit: int = 1000
    ) -> dict:
        """Aggregate latency/quality signals over the most recent queries."""
        from app.agent.prompts import ABSTENTION_MESSAGE

        stmt = (
            select(Query)
            .options(selectinload(Query.answer))
            .order_by(Query.created_at.desc())
            .limit(sample_limit)
        )
        if not include_all:
            stmt = stmt.where(Query.user_id == user_id)
        rows = list((await self.session.execute(stmt)).scalars().all())

        latencies = [int(row.latency_ms) for row in rows if row.latency_ms]
        verification: dict[str, int] = {}
        intents: dict[str, int] = {}
        abstained = 0
        for row in rows:
            if row.intent:
                intents[row.intent] = intents.get(row.intent, 0) + 1
            if row.answer is not None:
                status = str(row.answer.verification_status)
                verification[status] = verification.get(status, 0) + 1
                if row.answer.content.strip() == ABSTENTION_MESSAGE.strip():
                    abstained += 1
        total = len(rows)
        return {
            "total_queries": total,
            "latency_samples": len(latencies),
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
            "abstention_count": abstained,
            "abstention_rate": round(abstained / total, 4) if total else 0.0,
            "verification_breakdown": verification,
            "intent_breakdown": intents,
        }

    async def add_answer(self, answer: Answer) -> Answer:
        self.session.add(answer)
        await self.session.flush()
        return answer

    async def scrub_document_references(self, document_id: str) -> int:
        """Purge ``document_id`` text from every stored answer.

        Returns the number of answers whose stored evidence/citations changed.
        """
        rows = (await self.session.execute(select(Answer))).scalars().all()
        updated = 0
        for answer in rows:
            used = answer.used_evidence or []
            citations = answer.citations or []
            pruned_used = prune_document_references(used, document_id)
            pruned_citations = prune_document_references(citations, document_id)
            if len(pruned_used) != len(used) or len(pruned_citations) != len(citations):
                answer.used_evidence = pruned_used
                answer.citations = pruned_citations
                updated += 1
        if updated:
            await self.session.flush()
        return updated

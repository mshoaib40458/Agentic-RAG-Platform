"""Evaluation-run repository."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.evaluation import EvaluationRun
from app.repositories.base import BaseRepository


class EvaluationRepository(BaseRepository[EvaluationRun]):
    model = EvaluationRun

    async def list_recent(self, *, limit: int = 20, offset: int = 0) -> list[EvaluationRun]:
        stmt = (
            select(EvaluationRun)
            .order_by(EvaluationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

"""Evaluation service: create runs and trigger the runner."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import EvaluationStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.db.models.evaluation import EvaluationRun
from app.db.models.user import User
from app.evaluation.runner import EvaluationRunner
from app.repositories.evaluation_repo import EvaluationRepository
from app.schemas.evaluation import EvaluationCreate


class EvaluationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.repo = EvaluationRepository(session)

    async def create_run(self, payload: EvaluationCreate, *, user: User) -> EvaluationRun:
        eval_base_dir = Path(self.settings.eval_dataset_path).resolve().parent
        if payload.dataset_path:
            raw_path = Path(payload.dataset_path)
            target_path = (
                (eval_base_dir / raw_path).resolve()
                if not raw_path.is_absolute()
                else raw_path.resolve()
            )
            if not target_path.is_relative_to(eval_base_dir):
                raise BadRequestError(
                    "Evaluation dataset path must be located within the configured evaluation directory.",
                    code="invalid_dataset_path",
                )
            dataset_path = str(target_path)
        else:
            dataset_path = str(Path(self.settings.eval_dataset_path).resolve())

        run = EvaluationRun(
            dataset_version=payload.dataset_version,
            dataset_path=dataset_path,
            config=payload.config or {},
            status=EvaluationStatus.PENDING.value,
            created_by=user.id,
        )
        self.session.add(run)
        await self.session.flush()

        # Executed inline for the initial release. Moving this to a background
        # worker (SRS NFR-021) requires no changes to the runner contract.
        runner = EvaluationRunner(self.session)
        await runner.run(run)
        return run

    async def get_run(self, run_id: str) -> EvaluationRun:
        run = await self.repo.get(run_id)
        if run is None:
            raise NotFoundError("Evaluation run not found.")
        return run

    async def list_runs(self, *, limit: int, offset: int) -> tuple[list[EvaluationRun], int]:
        runs = await self.repo.list_recent(limit=limit, offset=offset)
        total = await self.repo.count()
        return runs, total

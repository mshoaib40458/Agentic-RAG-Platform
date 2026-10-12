"""Evaluation endpoints (SRS FR-048 / 5.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import PaginationDep, SessionDep, require_permission
from app.core.constants import Permission
from app.db.models.user import User
from app.schemas.common import Page
from app.schemas.evaluation import EvaluationCreate, EvaluationRead
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

EvalDep = Annotated[User, Depends(require_permission(Permission.EVALUATIONS_RUN))]


@router.post("", response_model=EvaluationRead, status_code=201)
async def create_evaluation(
    payload: EvaluationCreate, session: SessionDep, user: EvalDep
) -> EvaluationRead:
    run = await EvaluationService(session).create_run(payload, user=user)
    return EvaluationRead.model_validate(run)


@router.get("", response_model=Page[EvaluationRead])
async def list_evaluations(
    session: SessionDep, _: EvalDep, pagination: PaginationDep
) -> Page[EvaluationRead]:
    runs, total = await EvaluationService(session).list_runs(
        limit=pagination.limit, offset=pagination.offset
    )
    return Page(
        items=[EvaluationRead.model_validate(run) for run in runs],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get("/{run_id}", response_model=EvaluationRead)
async def get_evaluation(run_id: str, session: SessionDep, _: EvalDep) -> EvaluationRead:
    run = await EvaluationService(session).get_run(run_id)
    return EvaluationRead.model_validate(run)

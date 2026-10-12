"""Answer feedback endpoints (SRS FR-047)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.evaluation import FeedbackCreate, FeedbackRead
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRead, status_code=201)
async def submit_feedback(
    payload: FeedbackCreate, session: SessionDep, user: CurrentUser
) -> FeedbackRead:
    feedback = await FeedbackService(session).submit(payload, user=user)
    return FeedbackRead.model_validate(feedback)


@router.get("/query/{query_id}", response_model=list[FeedbackRead])
async def list_feedback(
    query_id: str, session: SessionDep, user: CurrentUser
) -> list[FeedbackRead]:
    feedback = await FeedbackService(session).list_for_query(query_id, user=user)
    return [FeedbackRead.model_validate(item) for item in feedback]

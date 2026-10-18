"""Health and readiness endpoints (SRS 5.2)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(session: SessionDep) -> HealthResponse:
    settings = get_settings()
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - report degraded rather than failing the probe
        database = "unavailable"

    vector_store = "ok"
    try:
        from app.retrieval.vector_store import get_vector_store

        await get_vector_store().count()
    except Exception:  # noqa: BLE001 - report degraded rather than failing the probe
        vector_store = "unavailable"

    is_ok = database == "ok" and vector_store == "ok"
    return HealthResponse(
        status="ok" if is_ok else "degraded",
        version=__version__,
        environment=settings.environment,
        database=database,
        vector_store=vector_store,
    )

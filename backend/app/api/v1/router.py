"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, documents, evaluations, feedback, health, query, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(query.router)
api_router.include_router(feedback.router)
api_router.include_router(evaluations.router)

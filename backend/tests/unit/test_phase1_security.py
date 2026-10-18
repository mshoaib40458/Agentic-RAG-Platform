"""Tests for Phase 1 security hardening and routing fixes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes import AgentNodes
from app.core.constants import UserRole, VerificationStatus
from app.core.exceptions import AuthenticationError, BadRequestError, NotFoundError
from app.db.models.query import Query
from app.db.models.user import User
from app.schemas.auth import UserCreate
from app.schemas.evaluation import EvaluationCreate
from app.services.auth_service import AuthService
from app.services.evaluation_service import EvaluationService
from app.services.feedback_service import FeedbackService


@pytest.mark.asyncio
async def test_evaluation_create_run_rejects_path_traversal():
    """create_run must reject dataset paths that traverse outside the eval directory."""
    session = AsyncMock()
    service = EvaluationService(session)

    evaluator = User(id="user-eval", role=UserRole.EVALUATOR.value, username="eval")
    traversal_payload = EvaluationCreate(
        dataset_version="v1",
        dataset_path="../../etc/passwd",
    )

    with pytest.raises(BadRequestError, match="Evaluation dataset path must be located"):
        await service.create_run(traversal_payload, user=evaluator)


@pytest.mark.asyncio
async def test_evaluation_create_run_rejects_absolute_path_traversal():
    """create_run must reject absolute paths pointing outside the eval directory."""
    session = AsyncMock()
    service = EvaluationService(session)

    evaluator = User(id="user-eval", role=UserRole.EVALUATOR.value, username="eval")
    abs_traversal_payload = EvaluationCreate(
        dataset_version="v1",
        dataset_path="C:\\Windows\\System32\\drivers\\etc\\hosts",
    )

    with pytest.raises(BadRequestError, match="Evaluation dataset path must be located"):
        await service.create_run(abs_traversal_payload, user=evaluator)


@pytest.mark.asyncio
async def test_auth_authenticate_timing_attack_protection():
    """verify_password must be called even when user does not exist to prevent timing attacks."""
    session = AsyncMock()
    service = AuthService(session)

    service.users.get_by_login = AsyncMock(return_value=None)

    with patch("app.services.auth_service.verify_password", return_value=False) as mock_verify:
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            await service.authenticate("nonexistent_user", "password123")

        assert mock_verify.called, "verify_password must be called even if user does not exist"


@pytest.mark.asyncio
async def test_auth_register_prevents_admin_privilege_escalation():
    """If an admin already exists, attempting to register with role=admin must be forced to user."""
    session = AsyncMock()
    service = AuthService(session)

    service.users.exists = AsyncMock(return_value=False)
    service.users.get_first_admin = AsyncMock(
        return_value=User(id="admin-1", role=UserRole.ADMIN.value, username="first_admin")
    )

    created_users = []

    async def mock_add(user):
        created_users.append(user)
        return user

    service.users.add = AsyncMock(side_effect=mock_add)

    payload = UserCreate(
        username="hacker",
        email="hacker@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    user = await service.register(payload)
    assert user.role == UserRole.USER.value, "Role must be downgraded to user when an admin exists"


@pytest.mark.asyncio
async def test_feedback_list_for_query_idor_protection():
    """A regular user must NOT be able to view feedback for a query they do not own."""
    session = AsyncMock()
    service = FeedbackService(session)

    query = Query(id="q1", user_id="owner-id", question="private question")
    service.queries.get = AsyncMock(return_value=query)

    other_user = User(id="attacker-id", role=UserRole.USER.value, username="attacker")

    with pytest.raises(NotFoundError, match="Query not found"):
        await service.list_for_query("q1", user=other_user)


@pytest.mark.asyncio
async def test_feedback_list_for_query_allows_owner_and_admin():
    """Query owner and admin/evaluator must be allowed to read query feedback."""
    session = AsyncMock()
    service = FeedbackService(session)

    query = Query(id="q1", user_id="owner-id", question="my question")
    service.queries.get = AsyncMock(return_value=query)
    service.feedback.for_query = AsyncMock(return_value=[])

    owner = User(id="owner-id", role=UserRole.USER.value, username="owner")
    admin = User(id="admin-id", role=UserRole.ADMIN.value, username="admin")
    evaluator = User(id="eval-id", role=UserRole.EVALUATOR.value, username="eval")

    assert await service.list_for_query("q1", user=owner) == []
    assert await service.list_for_query("q1", user=admin) == []
    assert await service.list_for_query("q1", user=evaluator) == []


def test_verify_routes_to_abstain_on_exhausted_unsupported():
    """route_after_verify must route to abstain when verification fails twice."""
    nodes = AgentNodes(retriever=object(), chat_model=object())

    unsupported_retry = {
        "verification_status": VerificationStatus.UNSUPPORTED.value,
        "generation_attempts": 1,
    }
    assert nodes.route_after_verify(unsupported_retry) == "generate"

    unsupported_exhausted = {
        "verification_status": VerificationStatus.UNSUPPORTED.value,
        "generation_attempts": 2,
    }
    assert nodes.route_after_verify(unsupported_exhausted) == "abstain"

    supported = {
        "verification_status": VerificationStatus.SUPPORTED.value,
        "generation_attempts": 2,
    }
    assert nodes.route_after_verify(supported) == "respond"

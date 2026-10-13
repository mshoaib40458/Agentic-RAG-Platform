"""Pytest fixtures.

Environment is configured *before* any application import so the cached
``Settings`` and the module-level async engine bind to an isolated temp DB.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="agentic_rag_test_"))
_DB_PATH = _TMP / "test.db"

os.environ["ENVIRONMENT"] = "development"
os.environ["SETTINGS_IGNORE_DOTENV"] = "1"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}"
os.environ["STORAGE_DIR"] = (_TMP / "storage").as_posix()
os.environ["QDRANT_PATH"] = (_TMP / "qdrant").as_posix()
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["RERANKER_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_TABLES = [
    "conversation_turns",
    "conversations",
    "answers",
    "feedback",
    "document_chunks",
    "documents",
    "queries",
    "evaluation_runs",
    "users",
]


def _clean_db() -> None:
    if not _DB_PATH.exists():
        return
    connection = sqlite3.connect(_DB_PATH)
    try:
        for table in _TABLES:
            with contextlib.suppress(sqlite3.OperationalError):
                connection.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table list
        connection.commit()
    finally:
        connection.close()


@pytest.fixture()
def client() -> TestClient:
    _clean_db()
    with TestClient(app) as test_client:
        yield test_client
    _clean_db()


@pytest.fixture(scope="session", autouse=True)
def _shutdown_services() -> None:
    """Release the cached Qdrant client so its destructor does not run during
    interpreter shutdown (which is noisy and can raise under Python 3.13)."""
    yield
    from app.retrieval.vector_store import get_vector_store, reset_vector_store

    get_vector_store().close()
    reset_vector_store()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def register_and_login(
    client: TestClient,
    *,
    username: str = "admin",
    email: str = "admin@example.com",
    password: str = "password123",
) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

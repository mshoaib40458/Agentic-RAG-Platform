"""Query endpoint guards and graceful degradation (SRS FR-032)."""

from __future__ import annotations

from app.core.exceptions import ProviderError
from tests.conftest import register_and_login


def test_query_requires_auth(client):
    response = client.post("/api/v1/query", json={"question": "hello"})
    assert response.status_code == 401


def test_query_rejects_empty_question(client):
    headers = register_and_login(client, username="querier", email="querier@example.com")
    response = client.post("/api/v1/query", json={"question": ""}, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_query_degrades_gracefully_when_provider_down(client, monkeypatch):
    """An upstream provider outage must fail in a bounded, well-formed way
    (a uniform error envelope) instead of crashing the process."""
    import app.retrieval.dense as dense_module

    def _raise():
        raise ProviderError("Embedding service unavailable.", code="embeddings_unavailable")

    monkeypatch.setattr(dense_module, "get_embedding_model", _raise)
    headers = register_and_login(client, username="querier2", email="querier2@example.com")
    response = client.post(
        "/api/v1/query", json={"question": "What is the billing policy?"}, headers=headers
    )
    assert response.status_code in (500, 502, 503)
    body = response.json()
    assert "error" in body and "code" in body["error"]

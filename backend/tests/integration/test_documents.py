"""Document upload validation and RBAC (SRS 4.2 / FR-002/FR-007)."""

from __future__ import annotations

from tests.conftest import register_and_login


def test_upload_rejects_unsupported_extension(client):
    headers = register_and_login(client, username="mgr", email="mgr@example.com")
    files = {"file": ("malware.exe", b"MZ binary", "application/octet-stream")}
    response = client.post("/api/v1/documents", files=files, headers=headers)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_upload_rejects_empty_file(client):
    headers = register_and_login(client, username="mgr2", email="mgr2@example.com")
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = client.post("/api/v1/documents", files=files, headers=headers)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "empty_file"


def test_upload_succeeds_and_serializes_timestamps(client, monkeypatch):
    """A successful upload must serialize ``updated_at`` (post-ingest refresh).

    Regression: the ingest pipeline's commit expires the ``updated_at``
    (``onupdate``) attribute, so returning the ORM object without refreshing it
    raised ``MissingGreenlet`` during ``DocumentRead.model_validate`` -> HTTP 500.
    """
    import app.ingestion.pipeline as pipeline

    class _StubEmbedding:
        dimension = 8

        async def embed_documents(self, texts):
            return [[0.1] * self.dimension for _ in texts]

    class _StubVectorStore:
        async def upsert(self, records):
            return None

        async def delete_by_document(self, document_id):
            return None

    monkeypatch.setattr(pipeline, "get_embedding_model", lambda: _StubEmbedding())
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: _StubVectorStore())

    headers = register_and_login(client, username="uploader", email="uploader@example.com")
    files = {"file": ("policy.txt", b"Paid annual leave is twenty days.", "text/plain")}
    response = client.post("/api/v1/documents", files=files, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "indexed"
    assert body["chunk_count"] == 1
    assert body["created_at"]
    assert body["updated_at"]


def test_document_list_empty_for_new_user(client):
    headers = register_and_login(client, username="mgr3", email="mgr3@example.com")
    response = client.get("/api/v1/documents", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_stats_endpoint(client):
    headers = register_and_login(client, username="mgr4", email="mgr4@example.com")
    response = client.get("/api/v1/documents/stats", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_plain_user_cannot_delete_documents(client):
    admin = register_and_login(client, username="admin", email="admin@example.com")
    client.post(
        "/api/v1/auth/register",
        json={"username": "plain", "email": "plain@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"username": "plain", "password": "password123"}
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.delete("/api/v1/documents/does-not-exist", headers=user_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"

    # Admin has the permission; unknown id yields 404 (not leaked as 403/500).
    admin_delete = client.delete("/api/v1/documents/does-not-exist", headers=admin)
    assert admin_delete.status_code == 404


def test_plain_user_cannot_list_users(client):
    register_and_login(client, username="admin", email="admin@example.com")
    client.post(
        "/api/v1/auth/register",
        json={"username": "plain2", "email": "plain2@example.com", "password": "password123"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"username": "plain2", "password": "password123"}
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/users", headers=user_headers)
    assert response.status_code == 403

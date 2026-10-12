"""Authentication and bootstrap behaviour (SRS 4.1)."""

from __future__ import annotations

from tests.conftest import register_and_login


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_first_user_becomes_admin(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "root", "email": "root@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"


def test_second_user_is_forced_to_user_role(client):
    register_and_login(client, username="admin", email="admin@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "password123",
            "role": "admin",  # attempt privilege escalation
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_login_returns_tokens_and_me_works(client):
    headers = register_and_login(client, username="alice", email="alice@example.com")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_duplicate_registration_conflicts(client):
    register_and_login(client, username="dup", email="dup@example.com")
    second = client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "other@example.com", "password": "password123"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_bad_credentials_rejected(client):
    register_and_login(client, username="carol", email="carol@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"username": "carol", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_missing_token_is_unauthorized(client):
    response = client.get("/api/v1/documents")
    assert response.status_code == 401

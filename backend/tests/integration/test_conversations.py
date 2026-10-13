"""Conversation endpoints: CRUD, auth, and ownership (SRS 4.4)."""

from __future__ import annotations

from tests.conftest import register_and_login


def test_conversations_require_auth(client):
    assert client.get("/api/v1/conversations").status_code == 401


def test_create_list_and_get_conversation(client):
    headers = register_and_login(client, username="chatty", email="chatty@example.com")

    created = client.post("/api/v1/conversations", json={}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["id"]
    assert body["title"] == "New chat"
    assert body["turn_count"] == 0

    listing = client.get("/api/v1/conversations", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == body["id"]

    detail = client.get(f"/api/v1/conversations/{body['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["turns"] == []


def test_conversation_is_private_to_owner(client):
    owner = register_and_login(client, username="owner", email="owner@example.com")
    created = client.post("/api/v1/conversations", json={}, headers=owner).json()

    other = register_and_login(client, username="other", email="other@example.com")

    assert client.get(f"/api/v1/conversations/{created['id']}", headers=other).status_code == 404
    assert (
        client.delete(f"/api/v1/conversations/{created['id']}", headers=other).status_code == 404
    )


def test_delete_conversation(client):
    headers = register_and_login(client, username="deleter", email="deleter@example.com")
    created = client.post("/api/v1/conversations", json={}, headers=headers).json()

    deleted = client.delete(f"/api/v1/conversations/{created['id']}", headers=headers)
    assert deleted.status_code == 204

    assert client.get(f"/api/v1/conversations/{created['id']}", headers=headers).status_code == 404
    assert client.get("/api/v1/conversations", headers=headers).json()["total"] == 0

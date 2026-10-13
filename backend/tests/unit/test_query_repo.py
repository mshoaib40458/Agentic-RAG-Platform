"""Answer-history scrubbing when a document is deleted (SRS FR-007)."""

from __future__ import annotations

from app.repositories.query_repo import prune_document_references


def test_prune_removes_only_matching_document():
    items = [
        {"document_id": "keep", "text": "alpha"},
        {"document_id": "drop", "text": "beta"},
        {"document_id": "keep", "text": "gamma"},
    ]
    pruned = prune_document_references(items, "drop")
    assert [item["text"] for item in pruned] == ["alpha", "gamma"]


def test_prune_handles_empty_and_untagged_entries():
    assert prune_document_references([], "drop") == []
    untagged = [{"text": "no document id"}]
    assert prune_document_references(untagged, "drop") == untagged

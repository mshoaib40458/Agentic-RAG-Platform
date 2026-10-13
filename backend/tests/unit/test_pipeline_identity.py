"""Deterministic chunk identity for idempotent ingestion (SRS NFR-006)."""

from __future__ import annotations

from app.ingestion.pipeline import _chunk_identity


def test_chunk_identity_is_deterministic():
    first = _chunk_identity("doc-1", 0)
    assert first == _chunk_identity("doc-1", 0)
    assert len(first) == 32


def test_chunk_identity_varies_by_document_and_index():
    assert _chunk_identity("doc-1", 0) != _chunk_identity("doc-1", 1)
    assert _chunk_identity("doc-1", 0) != _chunk_identity("doc-2", 0)

"""Configuration validation (SRS 6.5 / NFR-017)."""

from __future__ import annotations

import pytest

from app.core.config import DEFAULT_SECRET, Settings


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError, match="chunk_overlap"):
        Settings(chunk_size=100, chunk_overlap=200, _env_file=None)


def test_allowed_extensions_are_normalized():
    settings = Settings(allowed_extensions="PDF, .txt ,docx", _env_file=None)
    assert settings.allowed_extensions_set == {".pdf", ".txt", ".docx"}


def test_cors_origins_parsed():
    settings = Settings(
        cors_origins="http://a.test, http://b.test", _env_file=None
    )
    assert settings.cors_origins_list == ["http://a.test", "http://b.test"]


def test_production_requires_strong_secret():
    with pytest.raises(ValueError):
        Settings(environment="production", secret_key=DEFAULT_SECRET, _env_file=None)


def test_max_upload_bytes_conversion():
    settings = Settings(max_upload_mb=2, _env_file=None)
    assert settings.max_upload_bytes == 2 * 1024 * 1024

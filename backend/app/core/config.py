"""Application configuration.

All settings are sourced from environment variables (and an optional ``.env``
file) using ``pydantic-settings``. Field names map to upper-case env vars
case-insensitively, e.g. ``groq_api_key`` <- ``GROQ_API_KEY``.

List-like settings (CORS origins, allowed extensions) are declared as
comma-separated strings and exposed through normalized accessor properties.
This keeps the ``.env`` file readable while avoiding brittle JSON parsing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

DEFAULT_SECRET = "change-me-in-production-use-a-long-random-string"


class Settings(BaseSettings):
    """Strongly-typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Agentic RAG Platform"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Security ---
    secret_key: str = DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # --- File storage ---
    storage_dir: str = "./data/storage"
    max_upload_mb: int = 25
    allowed_extensions: str = ".pdf,.txt,.docx"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- LLM: Groq ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_temperature: float = 0.0
    groq_max_tokens: int = 1024
    groq_timeout_seconds: int = 30
    groq_max_retries: int = 3

    # --- Embeddings ---
    embedding_provider: Literal["local", "huggingface"] = "local"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_batch_size: int = 32
    hf_api_token: str = ""

    # --- Reranking ---
    # Disabled by default to keep first-run latency and disk usage low; enable
    # for a measurable precision lift on ambiguous queries. The cross-encoder
    # is warmed at startup when enabled (see app.main).
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_n: int = 5

    # --- Vector store ---
    vector_store: Literal["qdrant_local", "qdrant"] = "qdrant_local"
    qdrant_path: str = "./data/storage/qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "documents"

    # --- Chunking ---
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- Retrieval ---
    retrieval_top_k: int = 5
    retrieval_candidate_k: int = 20
    rrf_k: int = 60
    min_relevance_score: float = 0.15

    # --- Agent workflow ---
    agent_max_iterations: int = 8
    agent_max_retrievals: int = 3
    agent_timeout_seconds: int = 60
    agent_enable_query_decomposition: bool = True
    agent_enable_verification: bool = True

    # --- Evaluation ---
    eval_enabled: bool = False
    eval_dataset_path: str = "./data/eval/dataset.jsonl"

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Give the ``.env`` file priority over OS environment variables.

        Prevents a stale shell-level variable (e.g. an old ``GROQ_API_KEY``)
        from silently overriding the values the project is configured with.
        Tests opt out with ``SETTINGS_IGNORE_DOTENV=1`` so their environment
        overrides win.
        """
        ignore_dotenv = os.environ.get("SETTINGS_IGNORE_DOTENV", "").strip().lower()
        if ignore_dotenv in {"1", "true", "yes", "on"}:
            return (init_settings, env_settings, file_secret_settings)
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("chunk_overlap")
    @classmethod
    def _overlap_lt_size(cls, value: int, info) -> int:
        size = info.data.get("chunk_size", 0)
        if size and value >= size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return value

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> Settings:
        if self.environment == "production":
            if self.secret_key == DEFAULT_SECRET:
                raise ValueError("SECRET_KEY must be set to a strong value in production")
            if not self.groq_api_key:
                raise ValueError("GROQ_API_KEY must be configured in production")
        return self

    # ------------------------------------------------------------------ #
    # Derived accessors
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_extensions_set(self) -> set[str]:
        extensions: set[str] = set()
        for raw in self.allowed_extensions.split(","):
            ext = raw.strip().lower()
            if not ext:
                continue
            extensions.add(ext if ext.startswith(".") else f".{ext}")
        return extensions

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir).resolve()

    @property
    def upload_path(self) -> Path:
        return self.storage_path / "uploads"

    def ensure_directories(self) -> None:
        """Create storage directories required at runtime."""
        self.upload_path.mkdir(parents=True, exist_ok=True)
        Path(self.qdrant_path).resolve().mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (safe to use as a FastAPI dependency)."""
    return Settings()

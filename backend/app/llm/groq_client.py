"""Groq chat-completion client.

Wraps the async Groq SDK with:

* bounded retries + exponential backoff for transient failures (SRS NFR-004),
* a manual retry loop so only *retryable* errors are retried, and
* translation of provider errors into the application's error hierarchy so no
  Groq-specific detail (or secret) leaks past this boundary (SRS FR-032/NFR-011).

The ``groq`` SDK is imported lazily so the application can boot (and its
non-LLM endpoints be exercised) without the provider dependency installed.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.exceptions import ProviderError, RateLimitError
from app.llm.base import ChatResult, Message

logger = logging.getLogger(__name__)


class GroqChatModel:
    """Concrete :class:`~app.llm.base.ChatModel` backed by Groq."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.groq_api_key:
            raise ProviderError(
                "GROQ_API_KEY is not configured.", code="groq_not_configured"
            )
        try:
            from groq import AsyncGroq
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise ProviderError(
                "The 'groq' package is not installed.", code="groq_unavailable"
            ) from exc
        self._client = AsyncGroq(
            api_key=self._settings.groq_api_key,
            timeout=float(self._settings.groq_timeout_seconds),
            max_retries=0,  # retries handled below
        )

    @property
    def model_name(self) -> str:
        return self._settings.groq_model

    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        import groq

        settings = self._settings
        kwargs: dict = {
            "model": settings.groq_model,
            "messages": messages,
            "temperature": settings.groq_temperature if temperature is None else temperature,
            "max_tokens": settings.groq_max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        retryable = (groq.RateLimitError, groq.APITimeoutError, groq.APIConnectionError)
        delay = 0.5
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.chat.completions.create(**kwargs)
                return self._to_result(response)
            except groq.AuthenticationError as exc:
                raise ProviderError(
                    "Groq rejected the API credentials.", code="groq_auth_error"
                ) from exc
            except groq.BadRequestError as exc:
                raise ProviderError(
                    "Groq rejected the request parameters.", code="groq_bad_request"
                ) from exc
            except retryable as exc:
                if attempt >= settings.groq_max_retries:
                    logger.warning("groq_retries_exhausted", extra={"attempts": attempt})
                    raise RateLimitError(
                        "Groq is temporarily unavailable or rate limiting requests.",
                        code="groq_unavailable",
                    ) from exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8.0)
            except groq.APIStatusError as exc:
                status = getattr(exc, "status_code", 0)
                if status >= 500 and attempt < settings.groq_max_retries:
                    logger.warning("groq_server_error", extra={"status": status})
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise ProviderError(
                    "Groq returned an error response.", code="groq_error"
                ) from exc

    @staticmethod
    def _to_result(response: object) -> ChatResult:
        choice = response.choices[0]  # type: ignore[attr-defined]
        usage = getattr(response, "usage", None)
        return ChatResult(
            content=choice.message.content or "",
            model=getattr(response, "model", "") or "",
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            finish_reason=getattr(choice, "finish_reason", None),
        )


@lru_cache
def get_chat_model() -> GroqChatModel:
    """Process-wide cached chat model (lazy: constructs Groq client on first use)."""
    return GroqChatModel()

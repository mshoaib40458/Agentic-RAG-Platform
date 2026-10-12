"""Domain exceptions and consistent HTTP error handling.

Every application failure raises an :class:`AppError` subclass carrying a stable
machine-readable ``code`` and an HTTP ``status_code``. A single handler renders
them into a uniform envelope:

    {"error": {"code": "document_not_found", "message": "...", "details": {...}}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Starlette renamed these constants; resolve across versions so the app imports
# cleanly regardless of the installed version. The legacy names are only touched
# when the new ones are absent, avoiding deprecation warnings on modern Starlette.
def _status_code(new_name: str, legacy_name: str) -> int:
    value = getattr(status, new_name, None)
    if value is None:
        value = getattr(status, legacy_name)
    return int(value)


HTTP_413 = _status_code("HTTP_413_CONTENT_TOO_LARGE", "HTTP_413_REQUEST_ENTITY_TOO_LARGE")
HTTP_422 = _status_code(
    "HTTP_422_UNPROCESSABLE_CONTENT", "HTTP_422_UNPROCESSABLE_ENTITY"
)


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class DuplicateDocumentError(ConflictError):
    code = "duplicate_document"
    message = "A document with identical content has already been ingested."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_failed"
    message = "Authentication credentials are missing or invalid."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"
    message = "The request is malformed."


class PayloadTooLargeError(AppError):
    status_code = HTTP_413
    code = "payload_too_large"
    message = "The uploaded file exceeds the maximum allowed size."


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"
    message = "The uploaded file type is not supported."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "The upstream provider is rate limiting requests. Please retry shortly."


class ProviderError(AppError):
    """Upstream dependency (Groq, embeddings, vector store) failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"
    message = "An upstream service failed to respond."


class IngestionError(AppError):
    status_code = HTTP_422
    code = "ingestion_error"
    message = "The document could not be processed."


class RetrievalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "retrieval_error"
    message = "Retrieval failed while resolving the query."


class AgentError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "agent_error"
    message = "The agent workflow failed to complete."


def _error_response(
    *, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that convert exceptions into the uniform error envelope."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", extra={"code": exc.code, "detail": exc.message})
        return _error_response(
            status_code=exc.status_code, code=exc.code, message=exc.message, details=exc.details
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=HTTP_422,
            code="validation_error",
            message="Request validation failed.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code="http_error",
            message=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="An unexpected error occurred.",
        )

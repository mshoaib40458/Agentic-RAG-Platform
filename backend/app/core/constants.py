"""Shared enums and constants used across layers.

Kept deliberately dependency-free so both the persistence and API layers can
import from here without cycles.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Role-based access control roles (see SRS 2.2)."""

    ADMIN = "admin"
    DOCUMENT_MANAGER = "document_manager"
    USER = "user"
    EVALUATOR = "evaluator"


class DocumentStatus(StrEnum):
    """Lifecycle of an uploaded document (SRS FR-012)."""

    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class QueryStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    """Outcome of the answer-verification step (SRS FR-029)."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    SKIPPED = "skipped"


class QueryIntent(StrEnum):
    """Routing decision produced by the planning node (SRS FR-026/FR-034)."""

    DIRECT = "direct"              # single retrieval pass is sufficient
    MULTI_STEP = "multi_step"      # decompose + multi-hop retrieval
    NO_RETRIEVAL = "no_retrieval"  # meta/greeting, answer without documents
    CLARIFY = "clarify"            # ambiguous; ask the user to disambiguate


class EvaluationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Permission names used by the RBAC dependency. Keep explicit so routes read clearly.
class Permission(StrEnum):
    DOCUMENTS_READ = "documents:read"
    DOCUMENTS_WRITE = "documents:write"
    DOCUMENTS_DELETE = "documents:delete"
    QUERY = "query:execute"
    EVALUATIONS_RUN = "evaluations:run"
    USERS_MANAGE = "users:manage"


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.ADMIN: frozenset(Permission),
    UserRole.DOCUMENT_MANAGER: frozenset(
        {
            Permission.DOCUMENTS_READ,
            Permission.DOCUMENTS_WRITE,
            Permission.DOCUMENTS_DELETE,
            Permission.QUERY,
        }
    ),
    UserRole.USER: frozenset({Permission.DOCUMENTS_READ, Permission.QUERY}),
    UserRole.EVALUATOR: frozenset(
        {Permission.DOCUMENTS_READ, Permission.QUERY, Permission.EVALUATIONS_RUN}
    ),
}

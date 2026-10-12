"""Document management endpoints (SRS 4.2 / 5.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import PaginationDep, SessionDep, require_permission
from app.core.constants import DocumentStatus, Permission
from app.db.models.user import User
from app.schemas.common import Page
from app.schemas.document import DocumentRead, DocumentStats, DocumentUpdate
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

ReadDep = Annotated[User, Depends(require_permission(Permission.DOCUMENTS_READ))]
WriteDep = Annotated[User, Depends(require_permission(Permission.DOCUMENTS_WRITE))]
DeleteDep = Annotated[User, Depends(require_permission(Permission.DOCUMENTS_DELETE))]


@router.get("/stats", response_model=DocumentStats)
async def document_stats(session: SessionDep, user: ReadDep) -> DocumentStats:
    return await DocumentService(session).stats(user=user)


@router.get("", response_model=Page[DocumentRead])
async def list_documents(
    session: SessionDep,
    user: ReadDep,
    pagination: PaginationDep,
    category: str | None = None,
    collection: str | None = None,
    status_filter: DocumentStatus | None = None,
    search: str | None = None,
) -> Page[DocumentRead]:
    documents, total = await DocumentService(session).list_documents(
        user=user,
        category=category,
        collection=collection,
        status=status_filter.value if status_filter else None,
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page(
        items=[DocumentRead.model_validate(doc) for doc in documents],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    session: SessionDep,
    user: WriteDep,
    file: Annotated[UploadFile, File(description="PDF, TXT, or DOCX document")],
    category: Annotated[str | None, Form()] = None,
    collection: Annotated[str, Form()] = "default",
) -> DocumentRead:
    document = await DocumentService(session).create_document(
        upload=file, owner=user, category=category, collection=collection
    )
    return DocumentRead.model_validate(document)


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: str, session: SessionDep, user: ReadDep) -> DocumentRead:
    document = await DocumentService(session).get_document(document_id, user=user)
    return DocumentRead.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: str, payload: DocumentUpdate, session: SessionDep, user: WriteDep
) -> DocumentRead:
    document = await DocumentService(session).update_metadata(document_id, payload, user=user)
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, session: SessionDep, user: DeleteDep) -> Response:
    await DocumentService(session).delete_document(document_id, user=user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

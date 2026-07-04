import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.retention import DocumentRetentionRead, DocumentRetentionUpdateRequest
from app.services.retention import DocumentRetentionService

router = APIRouter(prefix="/api/documents", tags=["Document Retention"])


@router.get(
    "/{document_id}/retention",
    response_model=DocumentRetentionRead,
    summary="Get separated retention metadata for a document",
    responses={404: {"model": ErrorResponse}},
)
def get_document_retention(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentRetentionRead:
    return DocumentRetentionService(db, user.id).get_retention(document_id)


@router.put(
    "/{document_id}/retention",
    response_model=DocumentRetentionRead,
    summary="Update separated retention metadata for a document",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def put_document_retention(
    document_id: uuid.UUID,
    payload: DocumentRetentionUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentRetentionRead:
    return DocumentRetentionService(db, user.id).update_retention(document_id, payload)


@router.post(
    "/{document_id}/retention/suggest",
    response_model=DocumentRetentionRead,
    summary="Run an AI evaluation of the German paper-retention question for a document",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def suggest_document_retention(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentRetentionRead:
    return DocumentRetentionService(db, user.id).suggest_retention(document_id)


@router.post(
    "/{document_id}/retention/accept",
    response_model=DocumentRetentionRead,
    summary="Accept the current AI retention suggestion as-is",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def accept_document_retention_suggestion(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentRetentionRead:
    return DocumentRetentionService(db, user.id).accept_suggestion(document_id)


@router.post(
    "/{document_id}/retention/discard",
    response_model=DocumentRetentionRead,
    summary="Discard the current AI retention suggestion",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def discard_document_retention_suggestion(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentRetentionRead:
    return DocumentRetentionService(db, user.id).discard_suggestion(document_id)

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.document_types import (
    DocumentTypeCreateRequest,
    DocumentTypeListResponse,
    DocumentTypeRead,
    DocumentTypeUpdateRequest,
)
from app.services.document_types import DocumentTypeService

router = APIRouter(prefix="/api/document-types", tags=["Document Types"])


@router.get(
    "",
    response_model=DocumentTypeListResponse,
    summary="List document types",
)
def list_document_types(
    include_count: bool = Query(default=False, description="Include usage_count for each document type"),
    db: Session = Depends(get_db),
) -> DocumentTypeListResponse:
    service = DocumentTypeService(db)
    return DocumentTypeListResponse(items=service.list_document_types(include_count=include_count))


@router.post(
    "",
    response_model=DocumentTypeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document type",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_document_type(payload: DocumentTypeCreateRequest, db: Session = Depends(get_db)) -> DocumentTypeRead:
    service = DocumentTypeService(db)
    return DocumentTypeRead.model_validate(service.create_document_type(payload), from_attributes=True)


@router.patch(
    "/{document_type_id}",
    response_model=DocumentTypeRead,
    summary="Rename a document type",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_document_type(
    document_type_id: uuid.UUID, payload: DocumentTypeUpdateRequest, db: Session = Depends(get_db)
) -> DocumentTypeRead:
    service = DocumentTypeService(db)
    return DocumentTypeRead.model_validate(service.update_document_type(document_type_id, payload), from_attributes=True)


@router.delete(
    "/{document_type_id}",
    response_model=OkResponse,
    summary="Delete a document type",
    responses={404: {"model": ErrorResponse}},
)
def delete_document_type(document_type_id: uuid.UUID, db: Session = Depends(get_db)) -> OkResponse:
    service = DocumentTypeService(db)
    service.delete_document_type(document_type_id)
    return OkResponse(ok=True)

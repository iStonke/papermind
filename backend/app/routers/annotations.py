import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.annotations import (
    AnnotationCreateRequest,
    AnnotationListResponse,
    AnnotationRead,
    AnnotationUpdateRequest,
)
from app.schemas.common import ErrorResponse, OkResponse
from app.services.annotations import AnnotationService

router = APIRouter(tags=["Annotations"])


@router.get(
    "/api/documents/{document_id}/annotations",
    response_model=AnnotationListResponse,
    summary="List annotations for a document",
    responses={404: {"model": ErrorResponse}},
)
def list_annotations(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationListResponse:
    service = AnnotationService(db, user.id)
    items = service.list_by_document(document_id)
    return AnnotationListResponse(items=[AnnotationRead.model_validate(a) for a in items])


@router.post(
    "/api/documents/{document_id}/annotations",
    response_model=AnnotationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an annotation",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_annotation(
    document_id: uuid.UUID,
    payload: AnnotationCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationRead:
    service = AnnotationService(db, user.id)
    return AnnotationRead.model_validate(service.create(document_id, payload))


@router.patch(
    "/api/annotations/{annotation_id}",
    response_model=AnnotationRead,
    summary="Update an annotation (color, comment, link target)",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_annotation(
    annotation_id: uuid.UUID,
    payload: AnnotationUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnnotationRead:
    service = AnnotationService(db, user.id)
    return AnnotationRead.model_validate(service.update(annotation_id, payload))


@router.delete(
    "/api/annotations/{annotation_id}",
    response_model=OkResponse,
    summary="Delete an annotation",
    responses={404: {"model": ErrorResponse}},
)
def delete_annotation(
    annotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    service = AnnotationService(db, user.id)
    service.delete(annotation_id)
    return OkResponse()

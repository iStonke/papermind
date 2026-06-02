import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse
from app.schemas.correspondents import (
    CorrespondentAliasCreateRequest,
    CorrespondentCreateRequest,
    CorrespondentListResponse,
    CorrespondentRead,
)
from app.services.correspondents import CorrespondentService

router = APIRouter(prefix="/api/correspondents", tags=["Correspondents"])


@router.get(
    "",
    response_model=CorrespondentListResponse,
    summary="List correspondents",
)
def list_correspondents(
    include_count: bool = Query(default=False, description="Include usage_count for each correspondent"),
    db: Session = Depends(get_db),
) -> CorrespondentListResponse:
    service = CorrespondentService(db)
    items = service.list_correspondents(include_count=include_count)
    return CorrespondentListResponse(
        items=[CorrespondentRead.model_validate(item, from_attributes=True) for item in items]
    )


@router.post(
    "",
    response_model=CorrespondentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a correspondent",
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_correspondent(payload: CorrespondentCreateRequest, db: Session = Depends(get_db)) -> CorrespondentRead:
    service = CorrespondentService(db)
    return CorrespondentRead.model_validate(service.create_correspondent(payload), from_attributes=True)


@router.post(
    "/{correspondent_id}/aliases",
    response_model=CorrespondentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an alias to a correspondent",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def add_correspondent_alias(
    correspondent_id: uuid.UUID,
    payload: CorrespondentAliasCreateRequest,
    db: Session = Depends(get_db),
) -> CorrespondentRead:
    service = CorrespondentService(db)
    return CorrespondentRead.model_validate(service.add_alias(correspondent_id, payload.alias), from_attributes=True)

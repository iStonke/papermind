import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.saved_searches import (
    SavedSearchCreateRequest,
    SavedSearchListItem,
    SavedSearchListResponse,
    SavedSearchRead,
    SavedSearchUpdateRequest,
)
from app.services.saved_searches import SavedSearchService

router = APIRouter(prefix="/api/saved-searches", tags=["Smart Folders"])


@router.get(
    "",
    response_model=SavedSearchListResponse,
    summary="List smart folders",
)
def list_saved_searches(db: Session = Depends(get_db)) -> SavedSearchListResponse:
    service = SavedSearchService(db)
    items = service.list_saved_searches()
    return SavedSearchListResponse(
        items=[SavedSearchListItem.model_validate(item, from_attributes=True) for item in items]
    )


@router.get(
    "/{saved_search_id}",
    response_model=SavedSearchRead,
    summary="Get smart folder details",
    responses={404: {"model": ErrorResponse}},
)
def get_saved_search(saved_search_id: uuid.UUID, db: Session = Depends(get_db)) -> SavedSearchRead:
    service = SavedSearchService(db)
    saved_search = service.get_saved_search_or_404(saved_search_id)
    return SavedSearchRead.model_validate(saved_search, from_attributes=True)


@router.post(
    "",
    response_model=SavedSearchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create smart folder",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_saved_search(payload: SavedSearchCreateRequest, db: Session = Depends(get_db)) -> SavedSearchRead:
    service = SavedSearchService(db)
    saved_search = service.create_saved_search(payload)
    return SavedSearchRead.model_validate(saved_search, from_attributes=True)


@router.patch(
    "/{saved_search_id}",
    response_model=SavedSearchRead,
    summary="Update smart folder",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_saved_search(
    saved_search_id: uuid.UUID,
    payload: SavedSearchUpdateRequest,
    db: Session = Depends(get_db),
) -> SavedSearchRead:
    service = SavedSearchService(db)
    saved_search = service.update_saved_search(saved_search_id, payload)
    return SavedSearchRead.model_validate(saved_search, from_attributes=True)


@router.delete(
    "/{saved_search_id}",
    response_model=OkResponse,
    summary="Delete smart folder",
    responses={404: {"model": ErrorResponse}},
)
def delete_saved_search(saved_search_id: uuid.UUID, db: Session = Depends(get_db)) -> OkResponse:
    service = SavedSearchService(db)
    service.delete_saved_search(saved_search_id)
    return OkResponse(ok=True)

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.documents import DocumentListResponse
from app.schemas.smart_folders import (
    SmartFolderCreateRequest,
    SmartFolderListItem,
    SmartFolderListResponse,
    SmartFolderPreviewRequest,
    SmartFolderPreviewResponse,
    SmartFolderRead,
    SmartFolderSort,
    SmartFolderUpdateRequest,
)
from app.services.smart_folders import SmartFolderService

router = APIRouter(prefix="/api/smart-folders", tags=["Smart Folders"])


@router.get(
    "",
    response_model=SmartFolderListResponse,
    summary="List smart folders",
)
def list_smart_folders(db: Session = Depends(get_db)) -> SmartFolderListResponse:
    service = SmartFolderService(db)
    items = service.list_smart_folders()
    return SmartFolderListResponse(
        items=[SmartFolderListItem.model_validate(item, from_attributes=True) for item in items]
    )


@router.post(
    "/preview",
    response_model=SmartFolderPreviewResponse,
    response_model_exclude_none=True,
    summary="Preview a smart folder query",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def preview_smart_folder_documents(
    payload: SmartFolderPreviewRequest,
    db: Session = Depends(get_db),
) -> SmartFolderPreviewResponse:
    service = SmartFolderService(db)
    return service.preview_documents(
        payload.query_json,
        count_only=payload.count_only,
        limit=payload.limit,
        offset=payload.offset,
        sort=payload.sort,
    )


@router.get(
    "/{smart_folder_id}",
    response_model=SmartFolderRead,
    summary="Get smart folder details",
    responses={404: {"model": ErrorResponse}},
)
def get_smart_folder(smart_folder_id: uuid.UUID, db: Session = Depends(get_db)) -> SmartFolderRead:
    service = SmartFolderService(db)
    folder = service.get_smart_folder_or_404(smart_folder_id)
    return SmartFolderRead.model_validate(folder, from_attributes=True)


@router.post(
    "",
    response_model=SmartFolderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create smart folder",
    responses={400: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_smart_folder(payload: SmartFolderCreateRequest, db: Session = Depends(get_db)) -> SmartFolderRead:
    service = SmartFolderService(db)
    folder = service.create_smart_folder(payload)
    return SmartFolderRead.model_validate(folder, from_attributes=True)


@router.put(
    "/{smart_folder_id}",
    response_model=SmartFolderRead,
    summary="Update smart folder",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def update_smart_folder(
    smart_folder_id: uuid.UUID,
    payload: SmartFolderUpdateRequest,
    db: Session = Depends(get_db),
) -> SmartFolderRead:
    service = SmartFolderService(db)
    folder = service.update_smart_folder(smart_folder_id, payload)
    return SmartFolderRead.model_validate(folder, from_attributes=True)


@router.delete(
    "/{smart_folder_id}",
    response_model=OkResponse,
    summary="Delete smart folder",
    responses={404: {"model": ErrorResponse}},
)
def delete_smart_folder(smart_folder_id: uuid.UUID, db: Session = Depends(get_db)) -> OkResponse:
    service = SmartFolderService(db)
    service.delete_smart_folder(smart_folder_id)
    return OkResponse(ok=True)


@router.get(
    "/{smart_folder_id}/documents",
    response_model=DocumentListResponse,
    summary="Open smart folder and list matching documents",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def list_smart_folder_documents(
    smart_folder_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: SmartFolderSort = Query(default=SmartFolderSort.created_desc),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    service = SmartFolderService(db)
    return service.list_folder_documents(smart_folder_id, limit=limit, offset=offset, sort=sort)

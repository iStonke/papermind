import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.tags import (
    TagCreateRequest,
    TagDeleteBehavior,
    TagListResponse,
    TagMergeRequest,
    TagRead,
    TagUpdateRequest,
)
from app.services.tags import TagService

router = APIRouter(prefix="/api/tags", tags=["Tags"])


@router.get(
    "",
    response_model=TagListResponse,
    summary="List tags",
)
def list_tags(
    include_count: bool = Query(default=False, description="Include usage_count for each tag"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TagListResponse:
    service = TagService(db, user.id)
    return TagListResponse(items=service.list_tags(include_count=include_count))


@router.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_tag(payload: TagCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TagRead:
    service = TagService(db, user.id)
    return TagRead.model_validate(service.create_tag(payload), from_attributes=True)


@router.patch(
    "/{tag_id}",
    response_model=TagRead,
    summary="Rename a tag",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_tag(tag_id: uuid.UUID, payload: TagUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TagRead:
    service = TagService(db, user.id)
    return TagRead.model_validate(service.update_tag(tag_id, payload), from_attributes=True)


@router.post(
    "/{source_id}/merge",
    response_model=TagRead,
    summary="Merge one tag into another tag",
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def merge_tag(source_id: uuid.UUID, payload: TagMergeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TagRead:
    service = TagService(db, user.id)
    return TagRead.model_validate(service.merge_tag(source_id, payload), from_attributes=True)


@router.post(
    "/cleanup-unused",
    summary="Remove tags that are not attached to any document",
)
def cleanup_unused_tags(
    dry_run: bool = Query(
        default=False,
        description="If true, only return the tags that would be removed (no deletion).",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    service = TagService(db, user.id)
    return service.cleanup_unused_tags(dry_run=dry_run)


@router.delete(
    "/{tag_id}",
    response_model=OkResponse,
    summary="Delete a tag",
    responses={404: {"model": ErrorResponse}},
)
def delete_tag(
    tag_id: uuid.UUID,
    behavior: TagDeleteBehavior = Query(
        default=TagDeleteBehavior.detach,
        description="Detach relationships and delete tag",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkResponse:
    _ = behavior
    service = TagService(db, user.id)
    service.delete_tag(tag_id)
    return OkResponse(ok=True)

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.categories import (
    CategoryCreateRequest,
    CategoryListResponse,
    CategoryRead,
    CategoryUpdateRequest,
)
from app.schemas.common import ErrorResponse, OkResponse
from app.services.categories import CategoryService

router = APIRouter(prefix="/api/categories", tags=["Categories"])


@router.get(
    "",
    response_model=CategoryListResponse,
    summary="List categories",
)
def list_categories(
    include_count: bool = Query(default=False, description="Include usage_count for each category"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> CategoryListResponse:
    service = CategoryService(db, user.id)
    return CategoryListResponse(items=service.list_categories(include_count=include_count))


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_category(payload: CategoryCreateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> CategoryRead:
    service = CategoryService(db, user.id)
    return CategoryRead.model_validate(service.create_category(payload), from_attributes=True)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Rename a category",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_category(
    category_id: uuid.UUID, payload: CategoryUpdateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CategoryRead:
    service = CategoryService(db, user.id)
    return CategoryRead.model_validate(service.update_category(category_id, payload), from_attributes=True)


@router.delete(
    "/{category_id}",
    response_model=OkResponse,
    summary="Delete a category",
    responses={404: {"model": ErrorResponse}},
)
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> OkResponse:
    service = CategoryService(db, user.id)
    service.delete_category(category_id)
    return OkResponse(ok=True)

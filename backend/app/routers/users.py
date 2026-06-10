import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db import get_db
from app.models.user import User
from app.schemas.auth import UserRead
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.users import UserCreateRequest, UserListResponse, UserUpdateRequest
from app.services.users import UserService

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get(
    "",
    response_model=UserListResponse,
    summary="List all users (admin only)",
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> UserListResponse:
    service = UserService(db)
    items = service.list_users()
    return UserListResponse(items=[UserRead.model_validate(u, from_attributes=True) for u in items])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user (admin only)",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_user(
    payload: UserCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    service = UserService(db)
    user = service.create_user(payload)
    return UserRead.model_validate(user, from_attributes=True)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user (admin only)",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserRead:
    service = UserService(db)
    user = service.update_user(user_id, payload)
    return UserRead.model_validate(user, from_attributes=True)


@router.delete(
    "/{user_id}",
    response_model=OkResponse,
    summary="Delete a user (admin only)",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def delete_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OkResponse:
    service = UserService(db)
    service.delete_user(user_id)
    return OkResponse(ok=True)


@router.get(
    "/{user_id}/avatar",
    summary="Serve a user's profile picture (admin only)",
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_user_avatar(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    service = UserService(db)
    user = service.get_or_404(user_id)
    path = service.avatar_path(user)
    return FileResponse(path=path, media_type="image/webp", content_disposition_type="inline")

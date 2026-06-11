from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import create_access_token
from app.core.config import get_settings
from app.core.deps import get_current_user, token_secret
from app.core.errors import UnauthorizedError
from app.core.security import _client_identity, enforce_rate_limit
from app.db import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    FileTokenResponse,
    LoginRequest,
    ProfileUpdateRequest,
    TokenResponse,
    UserRead,
)
from app.schemas.common import ErrorResponse, OkResponse
from app.services.users import UserService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Short-lived token used only for native resource loads (image/PDF/download URLs)
# where the token must travel in the query string. Kept brief so a leak via
# access logs / browser history is only exploitable for a few minutes.
FILE_TOKEN_TTL_SECONDS = 300


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain an access token",
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    enforce_rate_limit(
        "login",
        _client_identity(request, payload.username),
        limit=10,
        window_seconds=300,
    )

    service = UserService(db)
    user = service.authenticate(payload.username, payload.password)
    if user is None:
        raise UnauthorizedError("Invalid username or password")

    settings = get_settings()
    ttl = settings.auth_token_ttl_seconds
    token = create_access_token(user.id, token_secret(), ttl)
    return TokenResponse(
        access_token=token,
        expires_in=ttl,
        user=UserRead.model_validate(user, from_attributes=True),
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
    responses={401: {"model": ErrorResponse}},
)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user, from_attributes=True)


@router.get(
    "/file-token",
    response_model=FileTokenResponse,
    summary="Issue a short-lived, file-scoped token for native resource URLs",
    responses={401: {"model": ErrorResponse}},
)
def file_token(user: User = Depends(get_current_user)) -> FileTokenResponse:
    token = create_access_token(
        user.id,
        token_secret(),
        FILE_TOKEN_TTL_SECONDS,
        scope="file",
    )
    return FileTokenResponse(token=token, expires_in=FILE_TOKEN_TTL_SECONDS)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update the current user's own profile (display name, e-mail)",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_me(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    service = UserService(db)
    updated = service.update_profile(user, payload)
    return UserRead.model_validate(updated, from_attributes=True)


@router.get(
    "/me/avatar",
    summary="Serve the current user's profile picture",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_my_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    service = UserService(db)
    path = service.avatar_path(user)
    return FileResponse(path=path, media_type="image/webp", content_disposition_type="inline")


@router.post(
    "/me/avatar",
    response_model=UserRead,
    summary="Upload/replace the current user's profile picture",
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
    },
)
async def upload_my_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    raw = await file.read()
    service = UserService(db)
    updated = service.set_avatar(user, raw, file.content_type)
    return UserRead.model_validate(updated, from_attributes=True)


@router.delete(
    "/me/avatar",
    response_model=UserRead,
    summary="Remove the current user's profile picture",
    responses={401: {"model": ErrorResponse}},
)
def delete_my_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserRead:
    service = UserService(db)
    updated = service.clear_avatar(user)
    return UserRead.model_validate(updated, from_attributes=True)


@router.post(
    "/change-password",
    response_model=OkResponse,
    summary="Change the password of the current user",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    service = UserService(db)
    service.change_password(user, payload.current_password, payload.new_password)
    return OkResponse(ok=True)


@router.post(
    "/logout",
    response_model=OkResponse,
    summary="Log out (client discards the token)",
)
def logout(_: User = Depends(get_current_user)) -> OkResponse:
    # Tokens are stateless; logout is handled client-side by discarding the token.
    return OkResponse(ok=True)

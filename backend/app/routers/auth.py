import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.core.auth import create_access_token, decode_access_token
from app.core.config import get_settings
from app.core.deps import get_current_user, token_secret
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import _client_identity, enforce_persistent_rate_limit
from app.db import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    FileTokenResponse,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    RefreshTokenRequest,
    SessionRead,
    StorageUsageResponse,
    TokenResponse,
    UserRead,
)
from app.schemas.common import ErrorResponse, OkResponse
from app.schemas.users import UserCreateRequest
from app.services.documents import DocumentService
from app.services.users import UserService
from app.services.auth_sessions import AuthSessionService
from app.models.auth_session import AuthSession

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Short-lived token used only for native resource loads (image/PDF/download URLs)
# where the token must travel in the query string. Kept brief so a leak via
# access logs / browser history is only exploitable for a few minutes.
FILE_TOKEN_TTL_SECONDS = 300


def _issue_token_response(user: User, session: AuthSession) -> TokenResponse:
    settings = get_settings()
    access_ttl = settings.auth_token_ttl_seconds
    refresh_ttl = settings.auth_refresh_token_ttl_seconds
    access_token = create_access_token(
        user.id,
        token_secret(),
        access_ttl,
        session_version=user.session_version,
        claims={"sid": str(session.id)},
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=access_ttl,
        refresh_expires_in=refresh_ttl,
        user=UserRead.model_validate(user, from_attributes=True),
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/api/auth",
    )


def _legacy_refresh_user(token: str, db: Session) -> User | None:
    token_payload = decode_access_token(token, token_secret())
    if not token_payload or token_payload.get("scope") != "refresh":
        return None
    try:
        user_id = uuid.UUID(str(token_payload.get("sub")))
    except (TypeError, ValueError):
        return None
    user = db.get(User, user_id)
    token_version = token_payload.get("sv")
    if (
        user is None
        or not user.is_active
        or not isinstance(token_version, int)
        or token_version != user.session_version
    ):
        return None
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain an access token",
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    enforce_persistent_rate_limit(
        db,
        "login",
        _client_identity(request, payload.username),
        limit=settings.auth_login_rate_limit,
        window_seconds=settings.auth_login_rate_window_seconds,
    )

    service = UserService(db)
    user = service.authenticate(payload.username, payload.password)
    if user is None:
        raise UnauthorizedError("Invalid username or password")

    session, refresh_token = AuthSessionService(db).create(user, request)
    _set_refresh_cookie(response, refresh_token)
    return _issue_token_response(user, session)


@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Register a new user and start a browser session",
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    enforce_persistent_rate_limit(
        db,
        "register",
        _client_identity(request, payload.username),
        limit=settings.auth_login_rate_limit,
        window_seconds=settings.auth_login_rate_window_seconds,
    )

    service = UserService(db)
    user = service.create_user(
        UserCreateRequest(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            email=payload.email,
            is_admin=False,
        )
    )
    session, refresh_token = AuthSessionService(db).create(user, request)
    _set_refresh_cookie(response, refresh_token)
    return _issue_token_response(user, session)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renew an authenticated browser session",
    responses={401: {"model": ErrorResponse}},
)
def refresh_session(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    cookie_token = request.cookies.get(settings.auth_cookie_name, "")
    service = AuthSessionService(db)
    rotated = service.rotate(cookie_token) if cookie_token else None
    if rotated is not None:
        session, user, refresh_token = rotated
        _set_refresh_cookie(response, refresh_token)
        return _issue_token_response(user, session)

    # One-release compatibility path: exchange the former stateless browser
    # refresh token for a server-side session and immediately move it to a
    # HttpOnly cookie.
    legacy_token = payload.refresh_token if payload else None
    user = _legacy_refresh_user(legacy_token or "", db)
    if user is None:
        raise UnauthorizedError("Session refresh expired")
    session, refresh_token = service.create(user, request)
    _set_refresh_cookie(response, refresh_token)
    return _issue_token_response(user, session)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
    responses={401: {"model": ErrorResponse}},
)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user, from_attributes=True)


@router.post(
    "/renew",
    response_model=TokenResponse,
    summary="Add refresh capability to an active session",
    responses={401: {"model": ErrorResponse}},
)
def renew_session(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    session, refresh_token = AuthSessionService(db).create(user, request)
    _set_refresh_cookie(response, refresh_token)
    return _issue_token_response(user, session)


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
        session_version=user.session_version,
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


@router.get(
    "/me/storage",
    response_model=StorageUsageResponse,
    summary="Owner-scoped storage footprint of the current user",
    responses={401: {"model": ErrorResponse}},
)
def my_storage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StorageUsageResponse:
    usage = DocumentService(db, user.id).storage_usage()
    return StorageUsageResponse.model_validate(usage)


@router.get(
    "/me/export",
    summary="Download a personal export (all own documents + metadata) as ZIP",
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}},
)
def my_export(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    tmp_path, archive_name, skipped = DocumentService(db, user.id).build_personal_export()
    return FileResponse(
        path=str(tmp_path),
        media_type="application/zip",
        filename=archive_name,
        content_disposition_type="attachment",
        background=BackgroundTask(lambda: Path(tmp_path).unlink(missing_ok=True)),
        headers={"X-Export-Skipped": str(skipped), "Cache-Control": "no-store"},
    )


@router.delete(
    "/me",
    response_model=OkResponse,
    summary="Delete the current user's own account (non-admins only)",
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def delete_me(
    payload: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    UserService(db).delete_self(user, payload.password)
    _clear_refresh_cookie(response)
    return OkResponse(ok=True)


def _current_session_id(request: Request) -> uuid.UUID | None:
    """Session id (``sid``) of the request's own access token, if present."""
    authorization = request.headers.get("authorization", "")
    scheme, _, access_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not access_token.strip():
        return None
    payload = decode_access_token(access_token.strip(), token_secret())
    try:
        return uuid.UUID(str(payload.get("sid"))) if payload else None
    except (TypeError, ValueError):
        return None


@router.get(
    "/sessions",
    response_model=list[SessionRead],
    summary="List the current user's active browser/device sessions",
    responses={401: {"model": ErrorResponse}},
)
def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionRead]:
    current_id = _current_session_id(request)
    sessions = AuthSessionService(db).list_active(user)
    return [
        SessionRead(
            id=session.id,
            user_agent=session.user_agent,
            client_ip=session.client_ip,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            current=session.id == current_id,
        )
        for session in sessions
    ]


@router.delete(
    "/sessions/{session_id}",
    response_model=OkResponse,
    summary="Revoke one of the current user's sessions",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def revoke_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    revoked = AuthSessionService(db).revoke_for_user(user, session_id)
    if not revoked:
        raise NotFoundError("Session not found", details={"session_id": str(session_id)})
    return OkResponse(ok=True)


@router.post(
    "/sessions/revoke-others",
    response_model=OkResponse,
    summary="Revoke all of the current user's sessions except this one",
    responses={401: {"model": ErrorResponse}},
)
def revoke_other_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    AuthSessionService(db).revoke_others(user, _current_session_id(request))
    return OkResponse(ok=True)


@router.post(
    "/logout",
    response_model=OkResponse,
    summary="Log out (client discards the token)",
)
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkResponse:
    settings = get_settings()
    service = AuthSessionService(db)
    cookie_token = request.cookies.get(settings.auth_cookie_name, "")
    if cookie_token:
        service.revoke_token(cookie_token)
    else:
        authorization = request.headers.get("authorization", "")
        _, _, access_token = authorization.partition(" ")
        payload = decode_access_token(access_token.strip(), token_secret())
        try:
            session_id = uuid.UUID(str(payload.get("sid"))) if payload else None
        except (TypeError, ValueError):
            session_id = None
        if session_id is not None:
            service.revoke_id(session_id)
    _clear_refresh_cookie(response)
    return OkResponse(ok=True)

"""FastAPI auth dependencies.

* :func:`get_current_user` / :func:`require_admin` resolve the authenticated
  user for individual routes.
* :func:`authenticate_request` is installed as an application-wide dependency in
  :mod:`app.main`. It enforces that every request is authenticated, while
  exempting public paths and allowing the existing machine-to-machine upload
  API key to keep working on the upload endpoints.
"""

from __future__ import annotations

import hmac
import logging
import re
import secrets
import uuid

from fastapi import Depends, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db import get_db
from app.models.user import User

logger = logging.getLogger("papermind.auth")

# Ephemeral signing secret used only when AUTH_SECRET_KEY is unset. Generated
# once per process; tokens signed with it become invalid after a restart.
_EPHEMERAL_SECRET = secrets.token_hex(32)

# Paths that never require authentication.
_EXEMPT_EXACT = {
    "/health",
    "/health/live",
    "/health/ready",
    "/api/health",
    "/api/auth/login",
    "/api/auth/refresh",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Upload endpoints that authenticate via the shared upload API key instead of a
# user session (scanners, drop scripts, ...).
_UPLOAD_PREFIXES = (
    "/api/direct-upload",
    "/api/import/inbox",
)

_FILE_TOKEN_PATHS = (
    re.compile(r"^/api/auth/me/avatar$"),
    re.compile(r"^/api/users/[0-9a-fA-F-]{36}/avatar$"),
    re.compile(r"^/api/documents/[0-9a-fA-F-]{36}/(?:file|thumbnail)$"),
)


def _allows_file_query_token(method: str, path: str) -> bool:
    return method.upper() == "GET" and any(pattern.fullmatch(path) for pattern in _FILE_TOKEN_PATHS)


def token_secret() -> str:
    return get_settings().auth_secret_key.strip() or _EPHEMERAL_SECRET


def _header_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    return None


def _query_token(request: Request) -> str | None:
    # Token via query param for native resource loads (<img>, PDF viewer,
    # downloads) that cannot set an Authorization header.
    query_token = request.query_params.get("token")
    return query_token.strip() if query_token else None


def _user_from_token(db: Session, token: str, *, allowed_scopes: set[str]) -> User | None:
    payload = decode_access_token(token, token_secret())
    if not payload:
        return None
    if payload.get("scope", "session") not in allowed_scopes:
        return None
    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        return None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    session_version = payload.get("sv")
    if not isinstance(session_version, int) or session_version != user.session_version:
        return None
    return user


def _default_user(db: Session) -> User | None:
    """Erster aktiver Admin – Fallback im Modus AUTH_ENABLED=false (Dev), damit
    die App trotz Pro-Benutzer-Trennung/RLS nutzbar bleibt (alles läuft als
    dieser Benutzer)."""
    return db.execute(
        select(User)
        .where(User.is_admin.is_(True), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()


def _resolve_user(request: Request, db: Session) -> User | None:
    # Dev-Modus ohne Auth: als erster Admin agieren (sonst blockt RLS alles).
    if not get_settings().auth_enabled:
        return _default_user(db)
    # Header bearer (the session token) — full access.
    header_token = _header_token(request)
    if header_token:
        user = _user_from_token(db, header_token, allowed_scopes={"session"})
        if user is not None:
            return user
    # Query-string token — ONLY short-lived file-scoped tokens are accepted here,
    # so a session token leaked via logs/history can never be used in a URL.
    query_token = _query_token(request)
    if (
        query_token
        and _allows_file_query_token(request.method, request.url.path)
    ):
        return _user_from_token(db, query_token, allowed_scopes={"file"})
    return None


def _has_valid_upload_key(request: Request) -> bool:
    configured = get_settings().direct_upload_api_key.strip()
    if not configured:
        return False
    supplied = request.headers.get("x-api-key")
    if not supplied:
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        supplied = token if scheme.lower() == "bearer" else ""
    return bool(supplied) and hmac.compare_digest(supplied.strip(), configured)


def _apply_owner_guc(db: Session, user: User) -> None:
    """Bindet den Owner für Row-Level Security an die Session. Das after_begin-Event
    (app/db/session.py) setzt app.owner_id daraus für JEDE Transaktion neu – auch
    für die, die nach einem commit() auf einer frisch aus dem Pool geholten
    Verbindung beginnen. Zusätzlich wird die bereits offene Transaktion sofort
    gesetzt, damit der aktuelle Request direkt abgesichert ist."""
    db.info["owner_id"] = str(user.id)
    try:
        db.execute(text("SELECT set_config('app.owner_id', :uid, true)"), {"uid": str(user.id)})
    except Exception:  # noqa: BLE001 - darf den Request nicht hart blockieren
        logger.exception("could not set app.owner_id for RLS")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated user or raise 401.

    Das Setzen von app.owner_id (RLS) erfolgt zentral in authenticate_request
    (globale Dependency, läuft vor jedem Endpoint) – hier daher kein zweiter
    set_config-Roundtrip.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        user = _resolve_user(request, db)
    if user is None:
        raise UnauthorizedError("Authentication required")
    request.state.user = user
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise ForbiddenError("Administrator privileges required")
    return user


def authenticate_request(request: Request, db: Session = Depends(get_db)) -> None:
    """Application-wide guard. No-op when auth is disabled."""
    settings = get_settings()
    if not settings.auth_enabled:
        # Trotzdem den Owner setzen, sonst blockt RLS im Dev-Modus alles.
        user = _resolve_user(request, db)
        if user is not None:
            request.state.user = user
            _apply_owner_guc(db, user)
        return

    path = request.url.path
    if path in _EXEMPT_EXACT:
        return

    user = _resolve_user(request, db)
    if user is not None:
        request.state.user = user
        _apply_owner_guc(db, user)
        return

    # Machine-to-machine upload endpoints may use the shared API key.
    if path.startswith(_UPLOAD_PREFIXES) and _has_valid_upload_key(request):
        return

    raise UnauthorizedError("Authentication required")

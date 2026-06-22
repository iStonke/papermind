from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth_session import AuthSession
from app.models.user import User


def _token_hash(secret: str) -> str:
    key = get_settings().auth_secret_key.encode("utf-8")
    return hmac.new(key, secret.encode("utf-8"), hashlib.sha256).hexdigest()


def _split_token(token: str) -> tuple[uuid.UUID, str] | None:
    session_id_raw, separator, secret = str(token or "").partition(".")
    if not separator or not secret:
        return None
    try:
        return uuid.UUID(session_id_raw), secret
    except ValueError:
        return None


def _client_ip(request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host[:64] if request.client else None


class AuthSessionService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, request) -> tuple[AuthSession, str]:
        settings = get_settings()
        session_id = uuid.uuid4()
        secret = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        session = AuthSession(
            id=session_id,
            user_id=user.id,
            token_hash=_token_hash(secret),
            session_version=user.session_version,
            user_agent=(request.headers.get("user-agent") or "")[:512] or None,
            client_ip=_client_ip(request),
            created_at=now,
            last_used_at=now,
            expires_at=now + timedelta(seconds=settings.auth_refresh_token_ttl_seconds),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session, f"{session_id}.{secret}"

    def rotate(self, token: str) -> tuple[AuthSession, User, str] | None:
        parsed = _split_token(token)
        if parsed is None:
            return None
        session_id, secret = parsed
        session = self.db.get(AuthSession, session_id, with_for_update=True)
        now = datetime.now(timezone.utc)
        if (
            session is None
            or session.revoked_at is not None
            or session.expires_at <= now
            or not hmac.compare_digest(session.token_hash, _token_hash(secret))
        ):
            self.db.rollback()
            return None
        user = self.db.get(User, session.user_id)
        if (
            user is None
            or not user.is_active
            or session.session_version != user.session_version
        ):
            session.revoked_at = now
            self.db.commit()
            return None
        next_secret = secrets.token_urlsafe(32)
        session.token_hash = _token_hash(next_secret)
        session.last_used_at = now
        self.db.commit()
        self.db.refresh(session)
        return session, user, f"{session.id}.{next_secret}"

    def revoke_token(self, token: str) -> None:
        parsed = _split_token(token)
        if parsed is None:
            return
        session_id, secret = parsed
        session = self.db.get(AuthSession, session_id)
        if session is None or not hmac.compare_digest(session.token_hash, _token_hash(secret)):
            return
        session.revoked_at = datetime.now(timezone.utc)
        self.db.commit()

    def revoke_id(self, session_id: uuid.UUID) -> None:
        session = self.db.get(AuthSession, session_id)
        if session is None or session.revoked_at is not None:
            return
        session.revoked_at = datetime.now(timezone.utc)
        self.db.commit()


def is_session_active(db: Session, session_id: uuid.UUID, user: User) -> bool:
    session = db.get(AuthSession, session_id)
    if session is None:
        return False
    now = datetime.now(timezone.utc)
    return (
        session.user_id == user.id
        and session.revoked_at is None
        and session.expires_at > now
        and session.session_version == user.session_version
    )

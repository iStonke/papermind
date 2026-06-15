import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import hash_password, verify_password
from app.core.config import get_settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.models.user import User
from app.schemas.auth import ProfileUpdateRequest
from app.schemas.users import UserCreateRequest, UserUpdateRequest
from app.services.utils import is_unique_violation

logger = logging.getLogger("papermind.users")

# Profile picture (avatar) constraints.
AVATAR_MAX_BYTES = 5 * 1024 * 1024
AVATAR_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
AVATAR_SIZE = 256
AVATAR_DIR = "avatars"


def process_avatar_image(raw: bytes) -> bytes:
    """Validate and normalize an uploaded avatar.

    Decodes the image, applies EXIF orientation, center-crops to a square,
    resizes to ``AVATAR_SIZE`` and re-encodes as WEBP (which also strips any
    embedded metadata). Raises :class:`BadRequestError` for non-images.
    """
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            # Center-crop to a square using the shorter edge.
            side = min(img.size)
            left = (img.width - side) // 2
            top = (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)

            out = io.BytesIO()
            img.save(out, format="WEBP", quality=85, method=6)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadRequestError("Uploaded file is not a valid image") from exc


def _normalize_username(raw: str) -> str:
    return " ".join((raw or "").split()).strip()


def _normalize_optional(raw: str | None) -> str | None:
    """Trim a free-text field; empty string becomes ``None`` (cleared)."""
    if raw is None:
        return None
    trimmed = raw.strip()
    return trimmed or None


def _normalize_email(raw: str | None) -> str | None:
    email = _normalize_optional(raw)
    if email is None:
        return None
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise BadRequestError("Invalid e-mail address", details={"email": email})
    return email


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def count(self) -> int:
        return self.db.execute(select(func.count(User.id))).scalar_one()

    def list_users(self) -> list[User]:
        stmt = select(User).order_by(func.lower(User.username).asc(), User.created_at.asc())
        return self.db.execute(stmt).scalars().all()

    def get_or_404(self, user_id: uuid.UUID) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found", details={"user_id": str(user_id)})
        return user

    def _email_in_use(self, email: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        stmt = select(func.count(User.id)).where(func.lower(User.email) == email.lower())
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return self.db.execute(stmt).scalar_one() > 0

    def get_by_username(self, username: str) -> User | None:
        normalized = _normalize_username(username)
        if not normalized:
            return None
        stmt = select(User).where(func.lower(User.username) == normalized.lower())
        return self.db.execute(stmt).scalars().first()

    def get_by_email_login(self, identifier: str) -> User | None:
        """Resolve a user by e-mail (case-insensitive). Nur für den Login-Fallback –
        ein '@' im Bezeichner genügt als Heuristik, um unnötige Queries für reine
        Benutzernamen zu vermeiden."""
        normalized = (identifier or "").strip()
        if not normalized or "@" not in normalized:
            return None
        stmt = select(User).where(func.lower(User.email) == normalized.lower())
        return self.db.execute(stmt).scalars().first()

    def authenticate(self, username: str, password: str) -> User | None:
        # Anmeldung per Benutzername ODER registrierter E-Mail. Benutzername hat
        # Vorrang (kein Verhaltenswechsel für bestehende Logins), E-Mail ist Fallback.
        user = self.get_by_username(username) or self.get_by_email_login(username)
        if user is None or not user.is_active:
            # Still run a hash to reduce username-enumeration timing differences.
            verify_password(password, "scrypt$16384$8$1$x$x")
            return None
        if not verify_password(password, user.password_hash):
            return None
        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_user(self, payload: UserCreateRequest) -> User:
        username = _normalize_username(payload.username)
        if not username:
            raise BadRequestError("Username must not be empty")

        email = _normalize_email(payload.email)
        if email is not None and self._email_in_use(email):
            raise ConflictError("E-mail already in use", details={"email": email})

        user = User(
            username=username,
            password_hash=hash_password(payload.password),
            display_name=_normalize_optional(payload.display_name),
            email=email,
            is_admin=bool(payload.is_admin),
            is_active=True,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc):
                raise ConflictError("Username already exists", details={"username": username}) from exc
            raise

        self.db.refresh(user)
        logger.info("user created id=%s username=%s admin=%s", user.id, user.username, user.is_admin)
        return user

    def update_user(self, user_id: uuid.UUID, payload: UserUpdateRequest) -> User:
        user = self.get_or_404(user_id)

        if payload.password is not None:
            user.password_hash = hash_password(payload.password)
        if payload.display_name is not None:
            user.display_name = _normalize_optional(payload.display_name)
        if payload.email is not None:
            email = _normalize_email(payload.email)
            if email is not None and self._email_in_use(email, exclude_id=user.id):
                raise ConflictError("E-mail already in use", details={"email": email})
            user.email = email
        if payload.is_admin is not None:
            self._guard_last_admin(user, will_be_admin=payload.is_admin, will_be_active=user.is_active)
            user.is_admin = payload.is_admin
        if payload.is_active is not None:
            self._guard_last_admin(user, will_be_admin=user.is_admin, will_be_active=payload.is_active)
            user.is_active = payload.is_active

        self.db.commit()
        self.db.refresh(user)
        logger.info("user updated id=%s username=%s", user.id, user.username)
        return user

    def update_profile(self, user: User, payload: ProfileUpdateRequest) -> User:
        """Self-service update of the current user's own profile fields."""
        if payload.display_name is not None:
            user.display_name = _normalize_optional(payload.display_name)
        if payload.email is not None:
            email = _normalize_email(payload.email)
            if email is not None and self._email_in_use(email, exclude_id=user.id):
                raise ConflictError("E-mail already in use", details={"email": email})
            user.email = email
        self.db.commit()
        self.db.refresh(user)
        logger.info("profile updated for user id=%s", user.id)
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise BadRequestError("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        self.db.commit()
        logger.info("password changed for user id=%s", user.id)

    # ── Avatar / profile picture ──────────────────────────────────────────────
    @staticmethod
    def _avatar_dir() -> Path:
        return Path(get_settings().storage_path) / AVATAR_DIR

    def set_avatar(self, user: User, raw: bytes, content_type: str | None) -> User:
        """Store a normalized profile picture for ``user``."""
        if content_type and content_type.split(";", 1)[0].strip().lower() not in AVATAR_ALLOWED_CONTENT_TYPES:
            raise BadRequestError(
                "Unsupported image type. Allowed: PNG, JPEG, WEBP",
                details={"content_type": content_type},
            )
        if len(raw) > AVATAR_MAX_BYTES:
            raise PayloadTooLargeError(
                "Uploaded image exceeds maximum allowed size",
                details={"max_bytes": AVATAR_MAX_BYTES},
            )
        if not raw:
            raise BadRequestError("Uploaded file is empty")

        processed = process_avatar_image(raw)

        avatar_dir = self._avatar_dir()
        avatar_dir.mkdir(parents=True, exist_ok=True)
        key = f"{AVATAR_DIR}/{user.id}.webp"
        destination = avatar_dir / f"{user.id}.webp"
        temp_path = destination.with_name(f"{destination.name}.uploading")
        temp_path.write_bytes(processed)
        temp_path.replace(destination)

        user.avatar_key = key
        self.db.commit()
        self.db.refresh(user)
        logger.info("avatar set for user id=%s", user.id)
        return user

    def clear_avatar(self, user: User) -> User:
        """Remove the user's profile picture (file + reference)."""
        if user.avatar_key:
            path = Path(get_settings().storage_path) / user.avatar_key
            path.unlink(missing_ok=True)
            user.avatar_key = None
            self.db.commit()
            self.db.refresh(user)
            logger.info("avatar cleared for user id=%s", user.id)
        return user

    def avatar_path(self, user: User) -> Path:
        """Resolve the stored avatar file path, or raise 404."""
        if not user.avatar_key:
            raise NotFoundError("User has no avatar", details={"user_id": str(user.id)})
        path = Path(get_settings().storage_path) / user.avatar_key
        if not path.is_file():
            raise NotFoundError("Avatar file missing", details={"user_id": str(user.id)})
        return path

    def delete_user(self, user_id: uuid.UUID, acting_user_id: uuid.UUID | None = None) -> None:
        if acting_user_id is not None and user_id == acting_user_id:
            raise ConflictError("Cannot delete your own account")
        user = self.get_or_404(user_id)
        if user.is_admin and user.is_active:
            self._guard_last_admin(user, will_be_admin=False, will_be_active=False)

        # Datei-Keys aller Dokumente des Benutzers VOR dem Löschen einsammeln.
        # Über eine System-Verbindung (umgeht RLS), da der löschende Admin die
        # Daten des Zielbenutzers per RLS sonst nicht sähe. Die DB-Zeilen werden
        # beim Löschen per ON DELETE CASCADE entfernt – die Dateien auf der
        # Platte müssen wir aber selbst aufräumen, sonst verwaisen sie.
        from app.db.session import SessionLocal
        from app.models.document import Document
        from app.models.document_file import DocumentFile
        from app.services.documents import DocumentService

        file_keys: set[str] = set()
        with SessionLocal() as sys_db:
            file_rows = sys_db.execute(
                select(DocumentFile.file_key)
                .join(Document, Document.id == DocumentFile.document_id)
                .where(Document.owner_id == user_id)
            ).scalars().all()
            file_keys.update(key for key in file_rows if key)
            storage_rows = sys_db.execute(
                select(Document.storage_key).where(Document.owner_id == user_id)
            ).scalars().all()
            file_keys.update(key for key in storage_rows if key)

        self.db.delete(user)
        self.db.commit()

        # Dateien best effort entfernen (Pfad-Resolver/-Cleanup aus DocumentService).
        cleaner = DocumentService(self.db)
        for key in file_keys:
            try:
                cleaner._cleanup_file(cleaner._resolve_storage_path(key))
            except Exception:  # noqa: BLE001 - Storage-Cleanup darf nie blockieren
                logger.warning("could not remove storage file for deleted user key=%s", key)

        logger.info(
            "user deleted id=%s username=%s storage_files_removed=%s",
            user_id,
            user.username,
            len(file_keys),
        )

    def _active_admin_count(self) -> int:
        stmt = select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
        return self.db.execute(stmt).scalar_one()

    def _guard_last_admin(self, user: User, *, will_be_admin: bool, will_be_active: bool) -> None:
        """Prevent removing/demoting the final active admin (lockout protection)."""
        is_currently_active_admin = user.is_admin and user.is_active
        will_remain_active_admin = will_be_admin and will_be_active
        if is_currently_active_admin and not will_remain_active_admin and self._active_admin_count() <= 1:
            raise ConflictError("Cannot remove the last active administrator")

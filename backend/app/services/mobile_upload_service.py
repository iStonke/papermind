import copy
import io
import logging
import os
import re
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, NotFoundError, PayloadTooLargeError, StorageError
from app.schemas.mobile_upload import (
    MobileUploadFileRead,
    MobileUploadFilesResponse,
    MobileUploadSessionCreateResponse,
    MobileUploadStatusResponse,
)
from app.services.import_staging import ImportStagingService
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.mobile_upload")
settings = get_settings()

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/webp",
    "image/tiff",
    "image/bmp",
}
ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
SESSION_STATES = {"open", "uploaded", "closed", "expired"}


@dataclass
class MobileUploadedFileEntry:
    id: str
    filename: str
    size: int
    content_type: str
    created_at: datetime
    source_file_id: str
    page_count: int
    target_stage_id: str | None = None


@dataclass
class MobileUploadSessionRecord:
    id: str
    token: str
    created_at: datetime
    expires_at: datetime
    status: str
    max_files: int
    target_stage_id: str | None = None
    files: list[MobileUploadedFileEntry] = field(default_factory=list)
    client_info: dict[str, str] = field(default_factory=dict)


def generate_session(
    *,
    max_files: int,
    target_stage_id: str | None = None,
    client_info: dict[str, str] | None = None,
) -> MobileUploadSessionRecord:
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.mobile_upload_session_ttl_minutes)
    return MobileUploadSessionRecord(
        id=str(uuid.uuid4()),
        token=secrets.token_urlsafe(32),
        created_at=now,
        expires_at=now + ttl,
        status="open",
        max_files=max_files,
        target_stage_id=(str(target_stage_id or "").strip() or None),
        files=[],
        client_info=client_info or {},
    )


def is_expired(session: MobileUploadSessionRecord, *, now: datetime | None = None) -> bool:
    check_time = now or datetime.now(timezone.utc)
    return check_time >= session.expires_at


def assert_session_valid(session: MobileUploadSessionRecord, token: str) -> None:
    if not token:
        raise BadRequestError("Upload token is required")
    if token != session.token:
        raise BadRequestError("Upload token is invalid")
    if session.status == "expired" or is_expired(session):
        session.status = "expired"
        raise BadRequestError("Upload session has expired")
    if session.status == "closed":
        raise BadRequestError("Upload session is already closed")
    if session.status not in SESSION_STATES:
        raise BadRequestError("Upload session is invalid")


class _InMemoryMobileUploadStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, MobileUploadSessionRecord] = {}

    def _cleanup_locked(self, now: datetime) -> None:
        purge_before = now - timedelta(hours=6)
        stale_ids: list[str] = []
        for session_id, session in self._sessions.items():
            if is_expired(session, now=now):
                session.status = "expired"
            if session.expires_at < purge_before:
                stale_ids.append(session_id)
        for session_id in stale_ids:
            self._sessions.pop(session_id, None)

    def create_session(
        self,
        *,
        max_files: int,
        target_stage_id: str | None,
        client_info: dict[str, str],
    ) -> MobileUploadSessionRecord:
        session = generate_session(max_files=max_files, target_stage_id=target_stage_id, client_info=client_info)
        with self._lock:
            now = datetime.now(timezone.utc)
            self._cleanup_locked(now)
            self._sessions[session.id] = session
            return copy.deepcopy(session)

    def _get_session_locked(self, session_id: str) -> MobileUploadSessionRecord:
        session = self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Upload session not found", details={"session_id": session_id})
        if is_expired(session):
            session.status = "expired"
        return session

    def get_session(self, session_id: str) -> MobileUploadSessionRecord:
        with self._lock:
            session = self._get_session_locked(session_id)
            return copy.deepcopy(session)

    def reserve_upload_slots(self, *, session_id: str, token: str, amount: int) -> MobileUploadSessionRecord:
        if amount <= 0:
            raise BadRequestError("At least one file is required")
        with self._lock:
            session = self._get_session_locked(session_id)
            assert_session_valid(session, token)
            remaining = max(0, session.max_files - len(session.files))
            if amount > remaining:
                raise BadRequestError(
                    "Upload limit reached for this session",
                    details={"remainingSlots": remaining, "maxFiles": session.max_files},
                )
            return copy.deepcopy(session)

    def append_uploaded_files(
        self,
        *,
        session_id: str,
        token: str,
        uploaded_files: list[MobileUploadedFileEntry],
        client_info: dict[str, str],
    ) -> MobileUploadSessionRecord:
        if not uploaded_files:
            raise BadRequestError("No valid files uploaded")

        with self._lock:
            session = self._get_session_locked(session_id)
            assert_session_valid(session, token)
            remaining = max(0, session.max_files - len(session.files))
            if len(uploaded_files) > remaining:
                raise BadRequestError(
                    "Upload limit reached for this session",
                    details={"remainingSlots": remaining, "maxFiles": session.max_files},
                )
            session.files.extend(uploaded_files)
            if client_info:
                session.client_info.update({key: value for key, value in client_info.items() if value})
            if len(session.files) >= session.max_files:
                session.status = "closed"
            elif session.files:
                session.status = "uploaded"
            else:
                session.status = "open"
            return copy.deepcopy(session)


_STORE = _InMemoryMobileUploadStore()


def _normalize_filename(filename: str, fallback: str = "upload.bin") -> str:
    raw = os.path.basename(str(filename or "").strip())
    if not raw:
        raw = fallback
    normalized = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .")
    return normalized or fallback


def _safe_pdf_filename(filename: str) -> str:
    normalized = _normalize_filename(filename, fallback="Dokument.pdf")
    stem = Path(normalized).stem or "Dokument"
    return f"{stem}.pdf"


def _read_upload_bytes(file: UploadFile) -> bytes:
    max_bytes = settings.upload_max_bytes
    file.file.seek(0)
    data = io.BytesIO()
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                "Uploaded file exceeds maximum allowed size",
                details={"max_bytes": max_bytes, "filename": file.filename},
            )
        data.write(chunk)
    file.file.seek(0)
    payload = data.getvalue()
    if not payload:
        raise BadRequestError("Uploaded file is empty", details={"filename": file.filename})
    return payload


def _classify_upload(filename: str, content_type: str, payload: bytes) -> str:
    ext = Path(filename).suffix.lower()
    normalized_type = content_type.strip().lower()

    if payload.startswith(b"%PDF-"):
        return "pdf"
    if ext == ".pdf":
        return "pdf"
    if normalized_type in ALLOWED_PDF_CONTENT_TYPES:
        return "pdf"
    if normalized_type.startswith("image/"):
        return "image"
    if normalized_type in ALLOWED_IMAGE_CONTENT_TYPES:
        return "image"
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"

    raise BadRequestError(
        "Unsupported file format. Only PDF and images are allowed.",
        details={"filename": filename, "content_type": content_type},
    )


def _image_to_pdf_bytes(payload: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(payload)) as image:
            converted = image.convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="PDF")
            result = output.getvalue()
    except UnidentifiedImageError as exc:
        raise BadRequestError("Image data is invalid or unsupported") from exc
    except OSError as exc:
        raise BadRequestError("Could not process uploaded image", details=str(exc)) from exc

    if not result.startswith(b"%PDF-"):
        raise BadRequestError("Image conversion failed")
    return result


def _mobile_upload_dir(session_id: str) -> Path:
    storage_root = Path(settings.storage_path).resolve()
    return (storage_root / "uploads" / "mobile" / session_id).resolve()


def _store_original_upload(*, session_id: str, filename: str, payload: bytes) -> Path:
    target_dir = _mobile_upload_dir(session_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_name = _normalize_filename(filename, fallback="upload.bin")
    target_path = target_dir / f"{timestamp}_{safe_name}"
    temp_path = target_path.with_suffix(f"{target_path.suffix}.uploading")

    try:
        with temp_path.open("wb") as handle:
            handle.write(payload)
        os.replace(temp_path, target_path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise StorageError("Failed to persist mobile upload", details=str(exc)) from exc

    return target_path


def _file_read_from_entry(entry: MobileUploadedFileEntry) -> MobileUploadFileRead:
    return MobileUploadFileRead(
        id=entry.id,
        filename=entry.filename,
        size=entry.size,
        contentType=entry.content_type,
        createdAt=entry.created_at,
        sourceFileId=entry.source_file_id,
        pageCount=entry.page_count,
        targetStageId=entry.target_stage_id,
    )


def _resolve_public_base_url(request: Request) -> str:
    configured = str(settings.public_web_base_url or "").strip()
    if configured:
        return configured.rstrip("/")

    origin = str(request.headers.get("origin") or "").strip()
    if origin and origin.lower() != "null":
        parts = urlsplit(origin)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}".rstrip("/")

    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


class MobileUploadService:
    def __init__(self, db: Session):
        self.db = db
        self.import_staging_service = ImportStagingService(db)

    def _normalize_max_files(self, requested_max_files: int | None) -> int:
        default_limit = max(1, int(settings.mobile_upload_default_max_files))
        hard_limit = max(1, int(settings.mobile_upload_max_files_limit))
        if requested_max_files is None:
            requested = default_limit
        else:
            requested = int(requested_max_files)
        return max(1, min(requested, hard_limit))

    def create_session(
        self,
        *,
        request: Request,
        max_files: int | None = None,
        target_stage_id: str | None = None,
    ) -> MobileUploadSessionCreateResponse:
        session = _STORE.create_session(
            max_files=self._normalize_max_files(max_files),
            target_stage_id=str(target_stage_id or "").strip() or None,
            client_info={
                "ua": str(request.headers.get("user-agent") or "").strip()[:200],
                "ip": str(request.client.host if request.client else "").strip()[:128],
            },
        )

        base_url = _resolve_public_base_url(request)
        upload_url = f"{base_url}/m/upload/{session.id}?t={session.token}"
        return MobileUploadSessionCreateResponse(
            sessionId=session.id,
            uploadUrl=upload_url,
            expiresAt=session.expires_at,
            targetStageId=session.target_stage_id,
        )

    def get_status(self, *, session_id: str, token: str | None = None) -> MobileUploadStatusResponse:
        session = _STORE.get_session(session_id)
        if token is not None and token != session.token:
            raise BadRequestError("Upload token is invalid")
        files = [_file_read_from_entry(entry) for entry in session.files]
        return MobileUploadStatusResponse(
            status=session.status,
            filesCount=len(files),
            files=files,
            expiresAt=session.expires_at,
            maxFiles=session.max_files,
        )

    def _to_staging_source(self, *, pdf_bytes: bytes, filename: str):
        staging_upload = UploadFile(filename=filename, file=io.BytesIO(pdf_bytes))
        try:
            result = self.import_staging_service.upload_sources([staging_upload])
        finally:
            try:
                staging_upload.file.close()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
        if not result.items:
            raise StorageError("Failed to register upload in import staging")
        return result.items[0]

    def _resolve_upload_flags(self) -> tuple[bool, bool]:
        try:
            app_settings = SettingsService(self.db).get_settings()
            return bool(app_settings.documents.auto_ocr), bool(app_settings.documents.auto_tagging)
        except Exception:  # pragma: no cover - db/runtime fallback
            return bool(settings.auto_ocr_on_upload), False

    def on_mobile_upload_received(self, source_file_id: str) -> None:
        ocr_auto, ai_autotag_auto = self._resolve_upload_flags()
        logger.info(
            "mobile upload received source_file_id=%s ocr_auto=%s ai_autotag_auto=%s",
            source_file_id,
            ocr_auto,
            ai_autotag_auto,
        )

    def upload_files(
        self,
        *,
        session_id: str,
        token: str,
        files: list[UploadFile],
        request: Request | None = None,
    ) -> MobileUploadFilesResponse:
        if not files:
            raise BadRequestError("At least one file is required")

        session_snapshot = _STORE.reserve_upload_slots(session_id=session_id, token=token, amount=len(files))
        target_stage_id = session_snapshot.target_stage_id

        uploaded_entries: list[MobileUploadedFileEntry] = []
        for upload in files:
            original_name = _normalize_filename(upload.filename or "scan-upload.bin")
            content_type = str(upload.content_type or "").strip().lower()
            payload = _read_upload_bytes(upload)
            upload_kind = _classify_upload(original_name, content_type, payload)
            _store_original_upload(session_id=session_id, filename=original_name, payload=payload)

            pdf_name = _safe_pdf_filename(original_name)
            if upload_kind == "pdf":
                if not payload.startswith(b"%PDF-"):
                    raise BadRequestError("File content is not a valid PDF", details={"filename": original_name})
                staged_pdf_bytes = payload
            else:
                staged_pdf_bytes = _image_to_pdf_bytes(payload)

            source = self._to_staging_source(pdf_bytes=staged_pdf_bytes, filename=pdf_name)
            uploaded_entry = MobileUploadedFileEntry(
                id=str(uuid.uuid4()),
                filename=original_name,
                size=len(payload),
                content_type=content_type or ("application/pdf" if upload_kind == "pdf" else "image/*"),
                created_at=datetime.now(timezone.utc),
                source_file_id=source.source_file_id,
                page_count=source.page_count,
                target_stage_id=target_stage_id,
            )
            uploaded_entries.append(uploaded_entry)
            self.on_mobile_upload_received(source.source_file_id)

        _STORE.append_uploaded_files(
            session_id=session_id,
            token=token,
            uploaded_files=uploaded_entries,
            client_info={
                "ua": str(request.headers.get("user-agent") or "").strip()[:200] if request else "",
                "ip": str(request.client.host if request and request.client else "").strip()[:128],
            },
        )
        return MobileUploadFilesResponse(ok=True, uploaded=len(uploaded_entries))

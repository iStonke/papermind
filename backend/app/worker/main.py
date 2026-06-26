import json
import logging
import os
import re
import socket
import subprocess
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.text import sanitize_text_for_db
from app.db.session import WorkerSessionLocal as SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_file import DocumentFile
from app.models.auth_session import AuthSession
from app.models.job import Job
from app.models.scanner import ScannerDeviceRecipient
from app.models.tag import Tag
from app.models.user import User
from app.services.deduplication import DocumentDeduplicationService
from app.services.document_dates import apply_ocr_document_date_result, extract_document_date_candidates
from app.services.embeddings import EmbeddingService
from app.services.documents import DocumentService
from app.services.import_inbox import ImportInboxService
from app.services.scanners import ScannerService
from app.services.ai_classification import apply_ollama_classification
from app.services.document_types import (
    document_type_hint_map,
    document_type_names,
    load_active_document_type_vocab,
)
from app.services.ocr_pipeline import run_ocr_pipeline
from app.services.settings import SettingsService

settings = get_settings()

logger = logging.getLogger("papermind.worker")
logging.basicConfig(level=logging.INFO)

WORKER_ID = (
    os.environ.get("WORKER_ID", "").strip()
    or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
)

AUTO_TAG_MAX_TAGS = 5
AUTO_TAG_MAX_TEXT_CHARS = 6000
TRASH_CLEANUP_INTERVAL_SECONDS = 3600
BACKUP_CHECK_INTERVAL_SECONDS = 60
JOB_RECLAIM_INTERVAL_SECONDS = 30
IMPORT_INBOX_PROCESSED_DIR = ".papermind-processed"
IMPORT_INBOX_PROCESSING_DIR = ".papermind-processing"
IMPORT_INBOX_FAILED_DIR = ".papermind-failed"
IMPORT_INBOX_OWNER_USERNAME = os.environ.get("IMPORT_INBOX_OWNER_USERNAME", "").strip()
IMPORT_INBOX_SCANNER_DEVICE_KEY = os.environ.get("IMPORT_INBOX_SCANNER_DEVICE_KEY", "flatbed-pi").strip()
IMPORT_INBOX_SCANNER_DEVICE_NAME = os.environ.get(
    "IMPORT_INBOX_SCANNER_DEVICE_NAME",
    "Canon LiDE 400 am Pi",
).strip()
AUTO_TAG_STOPWORDS = {
    "aber",
    "alle",
    "alles",
    "als",
    "also",
    "am",
    "an",
    "auch",
    "auf",
    "aus",
    "bei",
    "bin",
    "bis",
    "das",
    "dass",
    "dein",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "dies",
    "diese",
    "dieser",
    "doch",
    "dort",
    "ein",
    "eine",
    "einem",
    "einer",
    "eines",
    "er",
    "es",
    "etwas",
    "für",
    "hat",
    "haben",
    "hier",
    "ich",
    "ihm",
    "im",
    "in",
    "ist",
    "jede",
    "jeder",
    "kann",
    "kein",
    "keine",
    "mit",
    "nach",
    "nicht",
    "noch",
    "nur",
    "oder",
    "sein",
    "seine",
    "sich",
    "sie",
    "sind",
    "so",
    "und",
    "uns",
    "vom",
    "von",
    "vor",
    "war",
    "was",
    "weil",
    "wenn",
    "wer",
    "wie",
    "wir",
    "wird",
    "zu",
    "zum",
    "zur",
}


AUTO_TAG_BLOCKED_CANDIDATE_KEYS = {
    "keine information",
    "keine information gefunden",
    "keine informationen",
    "keine informationen gefunden",
    "keine infos",
    "keine infos gefunden",
    "keine tags",
    "keine tags gefunden",
    "keine schlagworte",
    "keine schlagwoerter",
    "keine schlagworte gefunden",
    "keine schlagwoerter gefunden",
    "keine relevanten informationen",
    "keine relevanten infos",
    "kein tag",
    "kein tag gefunden",
    "kein schlagwort",
    "kein schlagwort gefunden",
    "kein ergebnis",
    "nicht gefunden",
    "n a",
    "na",
    "none",
    "null",
    "unknown",
    "unbekannt",
}
AUTO_TAG_BLOCKED_CANDIDATE_PREFIXES = (
    "dazu finde ich keine information",
    "dazu finde ich keine infos",
    "ich finde keine information",
    "ich finde keine infos",
    "keine information",
    "keine infos",
    "keine tags",
    "keine schlagworte",
    "keine schlagwoerter",
    "keine schlagwörter",
    "kein tag",
    "kein schlagwort",
    "kein ergebnis",
)
AUTO_TAG_BLOCKED_CANDIDATE_CONTAINS = (
    "keine information",
    "keine infos",
    "keine relevanten information",
    "nicht gefunden",
    "finde ich keine",
    "finde keine",
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _storage_root() -> Path:
    return Path(settings.storage_path).resolve()


def _resolve_storage_path(file_key: str) -> Path:
    root = _storage_root()
    target = (root / file_key).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Invalid storage key")
    return target


def _truncate_error(message: str, max_length: int = 3500) -> str:
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."


def _find_document_file(document: Document, role: str) -> DocumentFile | None:
    for file_record in document.files:
        if file_record.role == role:
            return file_record
    return None


def _load_runtime_settings(db) -> dict:
    settings_payload = SettingsService(db).get_settings().model_dump(mode="json")
    return settings_payload


def _cleanup_expired_trash() -> None:
    try:
        with SessionLocal() as db:
            runtime_settings = SettingsService(db).get_settings()
            retention_days = int(runtime_settings.documents.trash_retention_days)
            if retention_days <= 0:
                return
            deleted_count = DocumentService(db).purge_expired_trash(retention_days)
            if deleted_count:
                logger.info("trash retention cleanup completed deleted_count=%s", deleted_count)
    except Exception as exc:  # pragma: no cover - defensive runtime cleanup
        logger.exception("trash retention cleanup failed err=%s", exc)


def _import_inbox_drop_root() -> Path | None:
    raw_path = str(settings.import_inbox_drop_path or "").strip()
    if not raw_path:
        return None
    return Path(raw_path).resolve()


def _import_inbox_subdir(name: str) -> Path | None:
    root = _import_inbox_drop_root()
    if root is None:
        return None
    return (root / name).resolve()


def _safe_drop_filename(filename: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._ -]+", "_", str(filename or "").strip()).strip(" .")
    return normalized or "Scan.pdf"


def _move_drop_file(source_path: Path, destination_dir: Path, *, prefix: str = "") -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_drop_filename(source_path.name)
    destination = (destination_dir / f"{prefix}{safe_name}").resolve()
    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        destination = destination.with_name(f"{stem}-{uuid.uuid4().hex[:8]}{suffix}")
    os.replace(source_path, destination)
    return destination


def _claim_next_import_inbox_pdf() -> tuple[Path, str] | None:
    root = _import_inbox_drop_root()
    processing_dir = _import_inbox_subdir(IMPORT_INBOX_PROCESSING_DIR)
    if root is None or processing_dir is None:
        return None
    root.mkdir(parents=True, exist_ok=True)
    processing_dir.mkdir(parents=True, exist_ok=True)

    now = time.time()
    stable_seconds = max(1, int(settings.import_inbox_file_stable_seconds))
    candidates = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() == ".pdf"
    )
    for source_path in candidates:
        try:
            stat = source_path.stat()
        except OSError:
            continue
        if stat.st_size <= 0:
            continue
        if now - stat.st_mtime < stable_seconds:
            continue
        original_name = source_path.name
        try:
            claimed_path = _move_drop_file(source_path, processing_dir, prefix=f"{uuid.uuid4().hex}-")
            return claimed_path, original_name
        except OSError:
            continue
    return None


def _default_owner_id(db) -> uuid.UUID | None:
    """Eigentümer für eingeworfene Inbox-Dateien.

    Scanner/SMB-Drops haben keinen Request-Kontext. Wenn konfiguriert, gewinnt
    IMPORT_INBOX_OWNER_USERNAME. Sonst nimm den zuletzt aktiv genutzten
    Admin-Account und falle für frische Installationen auf den ältesten aktiven
    Admin zurück.
    """
    if IMPORT_INBOX_OWNER_USERNAME:
        configured_owner = db.execute(
            select(User.id)
            .where(User.is_active.is_(True))
            .where(
                or_(
                    func.lower(User.username) == IMPORT_INBOX_OWNER_USERNAME.lower(),
                    func.lower(User.email) == IMPORT_INBOX_OWNER_USERNAME.lower(),
                )
            )
            .order_by(User.is_admin.desc(), User.created_at.asc())
            .limit(1)
        ).scalar()
        if configured_owner is not None:
            return configured_owner
        logger.warning("configured import inbox owner not found username=%s", IMPORT_INBOX_OWNER_USERNAME)

    active_admin = db.execute(
        select(User.id)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(User.is_admin.is_(True), User.is_active.is_(True))
        .where(AuthSession.revoked_at.is_(None))
        .where(AuthSession.expires_at > _now_utc())
        .order_by(AuthSession.last_used_at.desc(), AuthSession.created_at.desc())
        .limit(1)
    ).scalar()
    if active_admin is not None:
        return active_admin

    return db.execute(
        select(User.id)
        .where(User.is_admin.is_(True), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    ).scalar()


def _initial_scanner_recipient_id(db) -> uuid.UUID | None:
    if IMPORT_INBOX_OWNER_USERNAME:
        configured_owner = db.execute(
            select(User.id)
            .where(User.is_active.is_(True))
            .where(
                or_(
                    func.lower(User.username) == IMPORT_INBOX_OWNER_USERNAME.lower(),
                    func.lower(User.email) == IMPORT_INBOX_OWNER_USERNAME.lower(),
                )
            )
            .order_by(User.is_admin.desc(), User.created_at.asc())
            .limit(1)
        ).scalar()
        if configured_owner is not None:
            return configured_owner
        logger.warning("configured scanner recipient not found username=%s", IMPORT_INBOX_OWNER_USERNAME)

    return db.execute(
        select(User.id)
        .where(User.is_admin.is_(True), User.is_active.is_(True))
        .order_by(User.created_at.asc())
        .limit(1)
    ).scalar()


def _scanner_device_id_for_drop(db) -> uuid.UUID | None:
    if not IMPORT_INBOX_SCANNER_DEVICE_KEY:
        return None

    scanner = ScannerService(db).get_or_create_for_worker(
        IMPORT_INBOX_SCANNER_DEVICE_KEY,
        name=IMPORT_INBOX_SCANNER_DEVICE_NAME,
    )
    has_recipients = db.scalar(
        select(func.count(ScannerDeviceRecipient.user_id)).where(
            ScannerDeviceRecipient.scanner_device_id == scanner.id
        )
    )
    if int(has_recipients or 0) == 0:
        recipient_id = _initial_scanner_recipient_id(db)
        if recipient_id is not None:
            db.add(ScannerDeviceRecipient(scanner_device_id=scanner.id, user_id=recipient_id))
            db.flush()
            logger.info(
                "scanner device initial recipient configured device_key=%s recipient_id=%s",
                scanner.device_key,
                recipient_id,
            )
    return scanner.id


def _process_import_inbox_drop_file(claimed_path: Path, original_name: str) -> None:
    processed_dir = _import_inbox_subdir(IMPORT_INBOX_PROCESSED_DIR)
    failed_dir = _import_inbox_subdir(IMPORT_INBOX_FAILED_DIR)
    if processed_dir is None or failed_dir is None:
        return
    try:
        with SessionLocal() as db:
            scanner_device_id = _scanner_device_id_for_drop(db)
            if scanner_device_id is None:
                owner_id = _default_owner_id(db)
                owner_name = (
                    db.execute(select(User.username).where(User.id == owner_id)).scalar()
                    if owner_id is not None
                    else None
                )
                source_type = "shortcut"
            else:
                owner_id = None
                owner_name = None
                source_type = "scanner"
            result = ImportInboxService(db, owner_id).ingest_pdf_path(
                claimed_path,
                original_name=original_name,
                client_name="SMB",
                source_type=source_type,
                scanner_device_id=scanner_device_id,
            )
        created_count = len(result.items)
        _move_drop_file(claimed_path, processed_dir)
        logger.info(
            "import inbox drop processed file=%s items=%s source_type=%s scanner_device_id=%s owner=%s owner_id=%s",
            original_name,
            created_count,
            source_type,
            scanner_device_id,
            owner_name,
            owner_id,
        )
    except Exception as exc:
        logger.exception("import inbox drop failed file=%s err=%s", original_name, exc)
        try:
            _move_drop_file(claimed_path, failed_dir)
        except OSError:
            claimed_path.unlink(missing_ok=True)


def _has_active_job(db, document_id: uuid.UUID, job_type: str) -> bool:
    active_job = db.execute(
        select(Job.id).where(
            Job.document_id == document_id,
            Job.type == job_type,
            Job.status.in_(("queued", "running")),
        )
    ).scalar_one_or_none()
    return active_job is not None


def _queue_index_job(db, document: Document, *, reason: str) -> bool:
    if _has_active_job(db, document.id, "INDEX"):
        return False
    db.add(Job(document_id=document.id, type="INDEX", status="queued", progress=0))
    document.embedding_status = "queued"
    logger.info("index job queued document_id=%s reason=%s", document.id, reason)
    return True


def _queue_tag_job(db, document: Document, *, reason: str) -> bool:
    if _has_active_job(db, document.id, "TAG"):
        return False
    db.add(Job(document_id=document.id, type="TAG", status="queued", progress=0))
    logger.info("tag job queued document_id=%s reason=%s", document.id, reason)
    return True


def _normalize_tag_name(raw_value: str) -> str:
    cleaned = re.sub(r"[^A-Za-zÄÖÜäöüß0-9\-/ ]+", " ", str(raw_value or ""))
    normalized = " ".join(cleaned.split()).strip()
    if not normalized:
        return ""
    if len(normalized) > 48:
        normalized = normalized[:48].rstrip()
    return normalized


def _normalize_tag_key(raw_value: str) -> str:
    normalized = _normalize_tag_name(raw_value).lower()
    return re.sub(r"[^a-z0-9äöüß]+", " ", normalized).strip()


def _is_blocked_tag_candidate(candidate: str) -> bool:
    candidate_key = _normalize_tag_key(candidate)
    if not candidate_key:
        return True
    if candidate_key in AUTO_TAG_BLOCKED_CANDIDATE_KEYS:
        return True
    if any(candidate_key.startswith(prefix) for prefix in AUTO_TAG_BLOCKED_CANDIDATE_PREFIXES):
        return True
    return any(fragment in candidate_key for fragment in AUTO_TAG_BLOCKED_CANDIDATE_CONTAINS)


def _fallback_tag_candidates(text_value: str, max_tags: int = AUTO_TAG_MAX_TAGS) -> list[str]:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{2,}", text_value.lower())
    if not tokens:
        return []
    counts = Counter(
        token for token in tokens if token not in AUTO_TAG_STOPWORDS and not token.isnumeric() and len(token) >= 3
    )
    tags: list[str] = []
    for token, _ in counts.most_common(max_tags * 3):
        candidate = _normalize_tag_name(token)
        if not candidate:
            continue
        if _is_blocked_tag_candidate(candidate):
            continue
        label = candidate[0].upper() + candidate[1:]
        if label.lower() in {existing.lower() for existing in tags}:
            continue
        tags.append(label)
        if len(tags) >= max_tags:
            break
    return tags


def _suggest_tags_with_ai(text_value: str, max_tags: int = AUTO_TAG_MAX_TAGS) -> list[str]:
    normalized_text = " ".join(str(text_value or "").split()).strip()
    if not normalized_text:
        return []

    payload = {
        "model": "default",
        "system_prompt": (
            "Du extrahierst kurze deutsche Schlagwörter für Dokumente. "
            "Antworte nur mit einem JSON-Array von 1 bis 5 Strings ohne weitere Erklärungen."
        ),
        "max_sentences": 1,
        "max_tokens": 120,
        "temperature": 0.1,
        "question": "Extrahiere bis zu 5 prägnante Tags.",
        "user_prompt": (
            "Gib nur ein JSON-Array zurück, z.B. [\"Rechnung\", \"KFZ\", \"Versicherung\"].\n\n"
            f"TEXT:\n{normalized_text[:AUTO_TAG_MAX_TEXT_CHARS]}"
        ),
        "contexts": [],
    }

    try:
        response = httpx.post(
            f"{settings.ai_base_url.rstrip('/')}/chat",
            json=payload,
            timeout=settings.ai_chat_timeout_seconds,
        )
        response.raise_for_status()
        raw_answer = str(response.json().get("answer") or "").strip()
    except Exception as exc:  # pragma: no cover - network runtime path
        logger.warning("auto tagging ai call failed: %s", exc)
        return _fallback_tag_candidates(normalized_text, max_tags=max_tags)

    candidates: list[str] = []
    if raw_answer:
        array_match = re.search(r"\[[\s\S]*\]", raw_answer)
        candidate_text = array_match.group(0) if array_match else raw_answer
        try:
            import json

            parsed = json.loads(candidate_text)
            if isinstance(parsed, list):
                candidates = [str(item) for item in parsed]
        except Exception:
            split_candidates = re.split(r"[,;\n]", raw_answer)
            candidates = [part.strip(" -\t\r\n\"'") for part in split_candidates if part.strip()]

    has_ai_candidates = len(candidates) > 0
    normalized_candidates: list[str] = []
    seen = set()
    for candidate in candidates:
        normalized = _normalize_tag_name(candidate)
        if not normalized:
            continue
        if _is_blocked_tag_candidate(normalized):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized_candidates.append(normalized)
        if len(normalized_candidates) >= max_tags:
            break

    if normalized_candidates:
        return normalized_candidates
    if has_ai_candidates:
        return []
    return _fallback_tag_candidates(normalized_text, max_tags=max_tags)


def _get_or_create_tag(db, tag_name: str, owner_id) -> Tag | None:
    normalized_name = _normalize_tag_name(tag_name)
    if not normalized_name:
        return None
    if _is_blocked_tag_candidate(normalized_name):
        return None

    def _lookup():
        return db.execute(
            select(Tag).where(Tag.owner_id == owner_id, func.lower(Tag.name) == normalized_name.lower())
        ).scalar_one_or_none()

    existing = _lookup()
    if existing is not None:
        return existing

    try:
        with db.begin_nested():
            db.add(Tag(owner_id=owner_id, name=normalized_name))
            db.flush()
    except IntegrityError:
        pass

    return _lookup()


def _apply_tags_to_document(db, document: Document, tag_names: list[str]) -> tuple[int, list[str]]:
    if not tag_names:
        return 0, []

    existing_tag_ids = {tag.id for tag in document.tags}
    added = 0
    applied: list[str] = []
    for tag_name in tag_names:
        tag = _get_or_create_tag(db, tag_name, document.owner_id)
        if tag is None:
            continue
        if tag.id in existing_tag_ids:
            applied.append(tag.name)
            continue
        document.tags.append(tag)
        existing_tag_ids.add(tag.id)
        added += 1
        applied.append(tag.name)
    return added, applied


def _clear_job_lease(job: Job) -> None:
    job.worker_id = None
    job.lease_token = None
    job.heartbeat_at = None
    job.lease_expires_at = None


def _still_owns_job(db, job: Job, lease_token: uuid.UUID) -> bool:
    db.refresh(job, attribute_names=["status", "lease_token"])
    return job.status == "running" and job.lease_token == lease_token


def _heartbeat_job(job_id: uuid.UUID, lease_token: uuid.UUID) -> bool:
    now = _now_utc()
    lease_expires_at = now + timedelta(seconds=settings.worker_job_lease_seconds)
    with SessionLocal() as db:
        result = db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "running",
                Job.lease_token == lease_token,
            )
            .values(
                heartbeat_at=now,
                lease_expires_at=lease_expires_at,
            )
        )
        db.commit()
        return bool(result.rowcount)


@contextmanager
def _job_lease_heartbeat(job_id: uuid.UUID, lease_token: uuid.UUID):
    stop = threading.Event()

    def run_heartbeat() -> None:
        interval = min(
            settings.worker_job_heartbeat_seconds,
            max(5, settings.worker_job_lease_seconds // 3),
        )
        while not stop.wait(interval):
            try:
                if not _heartbeat_job(job_id, lease_token):
                    logger.warning("job lease lost job_id=%s worker_id=%s", job_id, WORKER_ID)
                    return
            except Exception:
                logger.exception("job heartbeat failed job_id=%s worker_id=%s", job_id, WORKER_ID)

    thread = threading.Thread(
        target=run_heartbeat,
        name=f"job-heartbeat-{job_id}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2)


def _mark_job_failed(job_id: uuid.UUID, reason: str, lease_token: uuid.UUID | None = None) -> None:
    with SessionLocal() as db:
        stmt = select(Job).where(Job.id == job_id)
        if lease_token is not None:
            stmt = stmt.where(Job.status == "running", Job.lease_token == lease_token)
        job = db.execute(stmt).scalar_one_or_none()
        if job is None:
            return

        document = db.get(Document, job.document_id)
        job.status = "failed"
        job.error_message = _truncate_error(reason)
        job.finished_at = _now_utc()
        if job.progress is None:
            job.progress = 0
        _clear_job_lease(job)

        if document is not None and job.type == "OCR":
            document.status = "failed"
            document.ocr_status = "failed"
            document.ocr_quality_status = "error"
            document.ocr_quality_message = _truncate_error(reason)
            document.ocr_confidence_score = None
            document.ocr_processing_seconds = None
        if document is not None and job.type == "INDEX":
            document.embedding_status = "failed"
            document.embedding_error = _truncate_error(reason)
            document.embedding_updated_at = _now_utc()

        db.commit()
        logger.error(
            "job failed job_id=%s document_id=%s type=%s error=%s",
            job_id,
            job.document_id,
            job.type,
            _truncate_error(reason, 500),
        )




def _claim_next_job() -> tuple[uuid.UUID, str, uuid.UUID] | None:
    with SessionLocal() as db:
        stmt = (
            select(Job)
            .where(Job.type.in_(("OCR", "INDEX", "TAG")), Job.status == "queued")
            .order_by(Job.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = db.execute(stmt).scalars().first()
        if job is None:
            return None

        document = db.get(Document, job.document_id)
        if document is None:
            job.status = "failed"
            job.error_message = "Document not found"
            job.finished_at = _now_utc()
            db.commit()
            return None

        job.status = "running"
        lease_token = uuid.uuid4()
        now = _now_utc()
        job.progress = 10 if job.type == "OCR" else 5
        job.started_at = now
        job.error_message = None
        job.worker_id = WORKER_ID
        job.lease_token = lease_token
        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=settings.worker_job_lease_seconds)
        if job.type == "OCR":
            document.status = "processing"
            document.ocr_status = "running"
        if job.type == "INDEX":
            document.embedding_status = "running"
            document.embedding_error = None

        db.commit()
        logger.info("job claimed job_id=%s document_id=%s type=%s", job.id, job.document_id, job.type)
        return job.id, job.type, lease_token


def _process_ocr_job(job_id: uuid.UUID, lease_token: uuid.UUID) -> None:
    try:
        with SessionLocal() as db:
            job = db.execute(
                select(Job)
                .where(Job.id == job_id, Job.lease_token == lease_token)
                .options(selectinload(Job.document))
            ).scalar_one_or_none()
            if job is None:
                return

            document = db.execute(
                select(Document)
                .where(Document.id == job.document_id)
                .options(selectinload(Document.files))
            ).scalar_one()

            original_file = _find_document_file(document, "original")
            if original_file is None and document.storage_key:
                original_file = DocumentFile(
                    document_id=document.id,
                    role="original",
                    file_key=document.storage_key,
                    filename="original.pdf",
                    mime_type="application/pdf",
                )
            if original_file is None:
                raise RuntimeError("Original PDF file record is missing")

            original_path = _resolve_storage_path(original_file.file_key)
            if not original_path.exists() or not original_path.is_file():
                raise RuntimeError("Original PDF file is missing in storage")

            ocr_key = f"{document.id}/ocr.pdf"
            ocr_path = _resolve_storage_path(ocr_key)
            runtime_settings = _load_runtime_settings(db)
            auto_tagging_enabled = bool(runtime_settings.get("documents", {}).get("auto_tagging", False))

            job.progress = 40
            db.commit()

            ocr_result = run_ocr_pipeline(
                original_path,
                ocr_path,
                runtime_settings,
                timeout_seconds=settings.worker_ocr_timeout_seconds,
            )
            if not _still_owns_job(db, job, lease_token):
                db.rollback()
                return
            quality_payload = dict(ocr_result.get("quality") or {})
            quality_status = str(quality_payload.get("status") or ocr_result.get("quality_status") or "").strip() or None
            confidence_score = quality_payload.get("confidence_score", ocr_result.get("confidence_score"))
            quality_message = str(quality_payload.get("message") or "").strip() or None
            processing_seconds = ocr_result.get("processing_time_seconds")

            job.progress = 70
            db.commit()

            extracted_text = str(ocr_result.get("text") or "")
            pages_payload = list(ocr_result.get("pages") or [])
            page_texts = [
                (int(item.get("page") or idx + 1), str(item.get("text") or "").strip())
                for idx, item in enumerate(pages_payload)
                if str(item.get("text") or "").strip()
            ]
            ocr_size = ocr_path.stat().st_size
            dedupe_service = DocumentDeduplicationService(db)
            logger.info(
                "ocr completion settings document_id=%s auto_ocr=%s auto_tagging=%s",
                document.id,
                bool(runtime_settings.get("documents", {}).get("auto_ocr", True)),
                auto_tagging_enabled,
            )

            ocr_file = _find_document_file(document, "ocr")
            if ocr_file is None:
                db.add(
                    DocumentFile(
                        document_id=document.id,
                        role="ocr",
                        file_key=ocr_key,
                        filename="ocr.pdf",
                        mime_type="application/pdf",
                        bytes=ocr_size,
                    )
                )
            else:
                ocr_file.file_key = ocr_key
                ocr_file.filename = "ocr.pdf"
                ocr_file.mime_type = "application/pdf"
                ocr_file.bytes = ocr_size

            job.progress = 90
            document.text_content = sanitize_text_for_db(extracted_text) or None
            document.text_source = "ocr"
            document.page_count = int(ocr_result.get("page_count") or document.page_count or 0) or document.page_count
            document.ocr_quality_status = quality_status
            document.ocr_confidence_score = float(confidence_score) if isinstance(confidence_score, (int, float)) else None
            document.ocr_quality_message = quality_message
            document.ocr_processing_seconds = float(processing_seconds) if isinstance(processing_seconds, (int, float)) else None
            existing_flags = dict(document.flags or {})
            existing_flags["ocr"] = {
                "engine_requested": ocr_result.get("engine_requested"),
                "engine_used": ocr_result.get("engine_used"),
                "quality": quality_payload,
                "processing_time_seconds": ocr_result.get("processing_time_seconds"),
                "page_metrics": [
                    {
                        "page": item.get("page"),
                        "confidence": item.get("confidence"),
                        "line_count": len(item.get("lines") or []),
                        "word_count": len(item.get("words") or []),
                    }
                    for item in pages_payload
                ],
            }
            document.flags = existing_flags
            extraction_result = extract_document_date_candidates(page_texts)
            date_applied = apply_ocr_document_date_result(document, extraction_result, overwrite_manual=False)
            logger.info(
                "document date extraction document_id=%s applied=%s best=%s confidence=%s candidates=%s",
                document.id,
                date_applied,
                extraction_result.best_date.isoformat() if extraction_result.best_date else None,
                extraction_result.best_confidence,
                len(extraction_result.candidates),
            )
            try:
                dedupe_service.evaluate_document_text_duplicate(document, extracted_text)
            except Exception as exc:  # pragma: no cover - best effort dedupe
                logger.warning("duplicate_text_check_failed document_id=%s error=%s", document.id, exc)
            doc_type_vocab = load_active_document_type_vocab(db)
            classification_warning = apply_ollama_classification(
                document,
                extracted_text=extracted_text,
                quality_status=quality_status,
                confidence_score=confidence_score,
                allowed_document_types=document_type_names(doc_type_vocab),
                document_type_hints=document_type_hint_map(doc_type_vocab),
                timeout_seconds=settings.ai_classification_timeout_seconds,
            )
            document.status = "ready"
            document.ocr_status = "done"
            if settings.index_auto_on_ready:
                _queue_index_job(db, document, reason="ocr_done")
            elif auto_tagging_enabled and (document.text_content or "").strip():
                _queue_tag_job(db, document, reason="ocr_done_no_index")
            job.status = "done"
            job.progress = 100
            job.error_message = classification_warning or (quality_message if quality_status in {"warning", "error"} else None)
            job.finished_at = _now_utc()
            _clear_job_lease(job)

            db.commit()
            logger.info(
                "ocr job completed job_id=%s document_id=%s text_bytes=%s engine=%s quality_status=%s confidence=%s quality=%s",
                job.id,
                document.id,
                len(extracted_text or ""),
                ocr_result.get("engine_used"),
                quality_status,
                confidence_score,
                ocr_result.get("quality"),
            )
            if quality_status in {"warning", "error"}:
                logger.warning(
                    "ocr quality issue document_id=%s status=%s confidence=%s message=%s",
                    document.id,
                    quality_status,
                    confidence_score,
                    quality_message,
                )
    except subprocess.TimeoutExpired:
        _mark_job_failed(
            job_id,
            f"OCR timed out after {settings.worker_ocr_timeout_seconds}s",
            lease_token,
        )
    except Exception as exc:  # pragma: no cover - infrastructure/runtime path
        _mark_job_failed(job_id, str(exc), lease_token)


def _process_index_job(job_id: uuid.UUID, lease_token: uuid.UUID) -> None:
    try:
        with SessionLocal() as db:
            job = db.execute(
                select(Job).where(Job.id == job_id, Job.lease_token == lease_token)
            ).scalar_one_or_none()
            if job is None:
                return

            document = db.get(Document, job.document_id)
            if document is None:
                raise RuntimeError("Document not found")

            service = EmbeddingService(db)
            stats = service.index_document(document.id)

            refreshed_job = db.get(Job, job_id)
            if refreshed_job is None or not _still_owns_job(db, refreshed_job, lease_token):
                db.rollback()
                return

            refreshed_job.status = "done"
            refreshed_job.progress = 100
            refreshed_job.error_message = None
            refreshed_job.finished_at = _now_utc()
            _clear_job_lease(refreshed_job)
            runtime_settings = _load_runtime_settings(db)
            auto_tagging_enabled = bool(runtime_settings.get("documents", {}).get("auto_tagging", False))
            logger.info(
                "index completion settings document_id=%s auto_tagging=%s",
                document.id,
                auto_tagging_enabled,
            )
            if auto_tagging_enabled and (document.text_content or "").strip():
                _queue_tag_job(db, document, reason="index_done")
            db.commit()

            chunk_count = db.scalar(
                select(func.count()).select_from(DocumentChunk).where(DocumentChunk.doc_id == document.id)
            ) or 0
            logger.info(
                "index job completed job_id=%s document_id=%s chunk_count=%s skipped=%s",
                job_id,
                document.id,
                int(chunk_count),
                bool(stats.get("skipped")),
            )
    except Exception as exc:  # pragma: no cover - infrastructure/runtime path
        _mark_job_failed(job_id, str(exc), lease_token)


def _process_tag_job(job_id: uuid.UUID, lease_token: uuid.UUID) -> None:
    try:
        with SessionLocal() as db:
            job = db.execute(
                select(Job).where(Job.id == job_id, Job.lease_token == lease_token)
            ).scalar_one_or_none()
            if job is None:
                return

            document = db.execute(
                select(Document)
                .where(Document.id == job.document_id)
                .options(selectinload(Document.tags))
            ).scalar_one_or_none()
            if document is None:
                raise RuntimeError("Document not found")

            runtime_settings = _load_runtime_settings(db)
            auto_tagging_enabled = bool(runtime_settings.get("documents", {}).get("auto_tagging", False))
            logger.info(
                "tag job started job_id=%s document_id=%s auto_tagging=%s",
                job_id,
                document.id,
                auto_tagging_enabled,
            )

            if not auto_tagging_enabled:
                job.status = "done"
                job.progress = 100
                job.error_message = None
                job.finished_at = _now_utc()
                _clear_job_lease(job)
                db.commit()
                return

            text_value = " ".join(str(document.text_content or "").split()).strip()
            if not text_value:
                job.status = "done"
                job.progress = 100
                job.error_message = None
                job.finished_at = _now_utc()
                _clear_job_lease(job)
                db.commit()
                logger.info("tag job skipped document_id=%s reason=no_text", document.id)
                return

            candidates = _suggest_tags_with_ai(text_value, max_tags=AUTO_TAG_MAX_TAGS)
            if not _still_owns_job(db, job, lease_token):
                db.rollback()
                return
            added_count, applied_names = _apply_tags_to_document(db, document, candidates)
            job.status = "done"
            job.progress = 100
            job.error_message = None
            job.finished_at = _now_utc()
            _clear_job_lease(job)
            db.commit()
            logger.info(
                "tag job completed job_id=%s document_id=%s suggested=%s applied=%s added=%s",
                job_id,
                document.id,
                candidates,
                applied_names,
                added_count,
            )
    except Exception as exc:  # pragma: no cover - infrastructure/runtime path
        _mark_job_failed(job_id, str(exc), lease_token)


def _reclaim_orphaned_jobs() -> None:
    """Jobs mit abgelaufener oder alter, lease-loser Ausführung zurückstellen.

    Der Sweep läuft beim Start und anschließend periodisch. Dadurch wird ein Job
    auch dann wieder aufgenommen, wenn der Container schneller neu startet als
    die Lease abläuft.
    """
    with SessionLocal() as db:
        orphaned = (
            db.execute(
                select(Job).where(
                    Job.type.in_(("OCR", "INDEX", "TAG")),
                    Job.status == "running",
                    or_(
                        Job.lease_expires_at.is_(None),
                        Job.lease_expires_at < _now_utc(),
                    ),
                )
            )
            .scalars()
            .all()
        )
        if not orphaned:
            return
        for job in orphaned:
            job.status = "queued"
            job.progress = 0
            job.started_at = None
            job.error_message = None
            _clear_job_lease(job)
            document = db.get(Document, job.document_id)
            if document is not None:
                if job.type == "OCR":
                    document.status = "processing"
                    document.ocr_status = "queued"
                elif job.type == "INDEX":
                    document.embedding_status = "queued"
        db.commit()
        logger.info(
            "reclaimed orphaned running jobs count=%s ids=%s",
            len(orphaned),
            [str(job.id) for job in orphaned],
        )


def _run_ocr_backfill() -> None:
    """Periodischer OCR-Backfill: reiht in kleinen Chargen OCR-Jobs für
    Dokumente ohne OCR ein und schließt so regelmäßig die Lücken. Über den
    Settings-Schalter ``documents.ocr_backfill_enabled`` an-/abschaltbar.
    """
    with SessionLocal() as db:
        try:
            app_settings = SettingsService(db).get_settings()
        except Exception:  # pragma: no cover - settings should always load
            logger.exception("ocr backfill: konnte Einstellungen nicht laden; übersprungen")
            return
        if not app_settings.documents.ocr_backfill_enabled:
            return
        result = DocumentService(db).backfill_ocr(
            limit=settings.ocr_backfill_batch_size,
            include_failed=True,
            max_retries=settings.ocr_backfill_max_retries,
        )
    if result.get("queued"):
        logger.info(
            "ocr backfill sweep queued=%s matched=%s skipped_active=%s skipped_retry=%s skipped_no_file=%s",
            result.get("queued"),
            result.get("matched"),
            result.get("skipped_active"),
            result.get("skipped_retry_limit"),
            result.get("skipped_missing_file"),
        )


def _run_backup_scheduler() -> None:
    """Stößt ein geplantes Backup an, sobald der konfigurierte Zeitpunkt fällig ist."""
    from datetime import datetime

    from sqlalchemy import select

    from app.models.backup_run import BackupRun
    from app.services.backup import BackupService, is_backup_due

    with SessionLocal() as db:
        try:
            service = BackupService(db)
            config = service.get_config()
            if not config.get("enabled"):
                return
            running = db.execute(select(BackupRun).where(BackupRun.status == "running").limit(1)).scalar_one_or_none()
            if running is not None:
                return
            last_scheduled = db.execute(
                select(BackupRun).where(BackupRun.kind == "scheduled").order_by(BackupRun.started_at.desc()).limit(1)
            ).scalar_one_or_none()
            last_at = last_scheduled.started_at if last_scheduled else None
            if not is_backup_due(config, now=datetime.now().astimezone(), last_run_at=last_at):
                return
        except Exception as exc:  # noqa: BLE001 - Scheduler darf den Worker nie abbrechen
            logger.warning("backup scheduler check failed: %s", exc)
            return
        logger.info("scheduled backup due -> running")
        try:
            service.run_backup(kind="scheduled")
        except Exception as exc:  # noqa: BLE001
            logger.warning("scheduled backup run failed: %s", exc)


def run() -> None:
    logger.info(
        "worker started worker_id=%s poll_interval=%ss lease=%ss heartbeat=%ss storage=%s",
        WORKER_ID,
        settings.worker_poll_interval_seconds,
        settings.worker_job_lease_seconds,
        settings.worker_job_heartbeat_seconds,
        settings.storage_path,
    )
    _reclaim_orphaned_jobs()
    last_trash_cleanup_at = 0.0
    last_ocr_backfill_at = 0.0
    last_backup_check_at = 0.0
    last_job_reclaim_at = time.monotonic()
    while True:
        now_monotonic = time.monotonic()
        if now_monotonic - last_job_reclaim_at >= JOB_RECLAIM_INTERVAL_SECONDS:
            last_job_reclaim_at = now_monotonic
            _reclaim_orphaned_jobs()

        if now_monotonic - last_trash_cleanup_at >= TRASH_CLEANUP_INTERVAL_SECONDS:
            last_trash_cleanup_at = now_monotonic
            _cleanup_expired_trash()

        if now_monotonic - last_ocr_backfill_at >= settings.ocr_backfill_interval_seconds:
            last_ocr_backfill_at = now_monotonic
            _run_ocr_backfill()

        if now_monotonic - last_backup_check_at >= BACKUP_CHECK_INTERVAL_SECONDS:
            last_backup_check_at = now_monotonic
            _run_backup_scheduler()

        # Inbox-Ordner-Import (SMB-Scanordner): eingeworfene PDFs landen als
        # Posteingang-Einträge (Eigentümer = erster Admin, Ein-Benutzer-Betrieb).
        inbox_drop_file = _claim_next_import_inbox_pdf()
        if inbox_drop_file is not None:
            claimed_path, original_name = inbox_drop_file
            _process_import_inbox_drop_file(claimed_path, original_name)
            continue

        claimed = _claim_next_job()
        if claimed is None:
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        job_id, job_type, lease_token = claimed
        with _job_lease_heartbeat(job_id, lease_token):
            if job_type == "OCR":
                _process_ocr_job(job_id, lease_token)
            elif job_type == "INDEX":
                _process_index_job(job_id, lease_token)
            elif job_type == "TAG":
                _process_tag_job(job_id, lease_token)
            else:
                _mark_job_failed(job_id, f"Unsupported job type {job_type}", lease_token)


if __name__ == "__main__":
    run()

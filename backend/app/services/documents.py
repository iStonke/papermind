import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only, noload, selectinload

from app.core.config import get_settings
from app.core.errors import (
    APIError,
    BadRequestError,
    ConflictError,
    DuplicateExactError,
    NotFoundError,
    PayloadTooLargeError,
    StorageError,
)
from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.document_retention import DocumentRetention
from app.models.document_type import DocumentType
from app.models.job import Job
from app.models.tag import Tag
from app.schemas.documents import (
    DocumentAttentionFilter,
    DocumentCreateRequest,
    DocumentDetail,
    DocumentFileRole,
    DocumentDateSource,
    DocumentListResponse,
    DocumentMetadataSuggestion,
    DocumentOCRStatus,
    DocumentSearchScope,
    DocumentSortField,
    DocumentStatus,
    DocumentStatusListResponse,
    DocumentTagReplaceRequest,
    DocumentTextSource,
    DocumentUpdateRequest,
    SortOrder,
)
from app.services.ai_classification import apply_ollama_classification
from app.services.document_types import (
    document_type_hint_map,
    document_type_names,
    load_active_document_type_vocab,
)
from app.services.document_storage import DocumentStorageService
from app.services.document_job_lifecycle import DocumentJobLifecycleService
from app.services.document_query_service import DocumentQueryService
from app.services.correspondent_matching import CorrespondentMatchingService
from app.services.job_queue import enqueue_document_job, has_active_document_job
from app.services.retention import _compute_retain_until
from app.services.settings import SettingsService
from app.services.tag_suggestions import (
    fallback_tag_candidates,
    is_blocked_tag_candidate,
    normalize_tag_key,
    normalize_tag_name,
    suggest_tags_with_ai,
)
from app.services.utils import is_unique_violation

logger = logging.getLogger("papermind.documents")
settings = get_settings()

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
}
AUTO_TAG_MAX_SUGGESTIONS = 3
AUTO_TAG_MAX_TEXT_CHARS = 8000
class DocumentService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id
        self.storage = DocumentStorageService(
            storage_path=settings.storage_path,
            upload_max_bytes=settings.upload_max_bytes,
            text_check_pages=settings.text_check_pages,
        )
        self.job_lifecycle = DocumentJobLifecycleService(db)
        self.query = DocumentQueryService(db, owner_id)

    def _scope(self, stmt):
        """Beschränkt eine Document-Query auf den aktuellen Owner (sofern gesetzt)."""
        if self.owner_id is not None:
            return stmt.where(Document.owner_id == self.owner_id)
        return stmt

    def _scope_tags(self, stmt):
        """Beschränkt eine Tag-Query auf den aktuellen Owner (sofern gesetzt)."""
        if self.owner_id is not None:
            return stmt.where(Tag.owner_id == self.owner_id)
        return stmt

    @staticmethod
    def _summary_load_options():
        """Compatibility shim for consumers that still use DocumentService."""
        return DocumentQueryService.summary_load_options()

    def _normalize_auto_tag_name(self, raw_value: str) -> str:
        return normalize_tag_name(raw_value)

    def _normalize_auto_tag_key(self, raw_value: str) -> str:
        return normalize_tag_key(raw_value)

    def _is_blocked_auto_tag_candidate(self, candidate: str) -> bool:
        return is_blocked_tag_candidate(candidate)

    def _fallback_auto_tag_candidates(self, text_value: str, max_tags: int = AUTO_TAG_MAX_SUGGESTIONS) -> list[str]:
        return fallback_tag_candidates(text_value, max_tags=max_tags)

    def _suggest_auto_tags_with_ai(self, text_value: str, max_tags: int = AUTO_TAG_MAX_SUGGESTIONS) -> list[str]:
        return suggest_tags_with_ai(
            text_value,
            max_tags=max_tags,
            max_text_chars=AUTO_TAG_MAX_TEXT_CHARS,
            ai_base_url=settings.ai_base_url,
            timeout_seconds=settings.ai_chat_timeout_seconds,
        )

    def _resolve_existing_tags_for_candidates(self, candidates: list[str], existing_tags: list[Tag]) -> list[Tag]:
        if not candidates or not existing_tags:
            return []

        exact_map: dict[str, Tag] = {}
        existing_keys: dict[uuid.UUID, str] = {}
        for tag in existing_tags:
            key = self._normalize_auto_tag_key(tag.name)
            if not key:
                continue
            existing_keys[tag.id] = key
            exact_map.setdefault(key, tag)

        matches: list[Tag] = []
        seen_ids: set[uuid.UUID] = set()
        for candidate in candidates:
            candidate_key = self._normalize_auto_tag_key(candidate)
            if not candidate_key:
                continue

            matched = exact_map.get(candidate_key)
            if matched is None:
                for tag in existing_tags:
                    tag_key = existing_keys.get(tag.id, "")
                    if not tag_key:
                        continue
                    if candidate_key in tag_key or tag_key in candidate_key:
                        matched = tag
                        break

            if matched is None or matched.id in seen_ids:
                continue
            seen_ids.add(matched.id)
            matches.append(matched)
            if len(matches) >= AUTO_TAG_MAX_SUGGESTIONS:
                break

        return matches

    def _get_or_create_tag_case_insensitive(self, tag_name: str) -> tuple[Tag | None, bool]:
        normalized_name = self._normalize_auto_tag_name(tag_name)
        if not normalized_name:
            return None, False
        if self._is_blocked_auto_tag_candidate(normalized_name):
            return None, False

        def _lookup():
            stmt = select(Tag).where(func.lower(Tag.name) == normalized_name.lower())
            if self.owner_id is not None:
                stmt = stmt.where(Tag.owner_id == self.owner_id)
            return self.db.execute(stmt).scalar_one_or_none()

        existing = _lookup()
        if existing is not None:
            return existing, False

        created = False
        try:
            with self.db.begin_nested():
                self.db.add(Tag(owner_id=self.owner_id, name=normalized_name))
                self.db.flush()
                created = True
        except IntegrityError:
            created = False

        tag = _lookup()
        return tag, created and tag is not None

    def _extract_text_for_manual_auto_tagging(self, document: Document) -> str:
        text_value = " ".join(sanitize_text_for_db(str(document.text_content or "")).split()).strip()
        if text_value:
            return text_value[:AUTO_TAG_MAX_TEXT_CHARS]

        for role in (DocumentFileRole.ocr, DocumentFileRole.original):
            try:
                _, _, source_path = self.get_document_file_by_role(document.id, role)
            except NotFoundError:
                continue
            except Exception:
                continue

            try:
                reader = PdfReader(str(source_path))
                collected: list[str] = []
                current_len = 0
                for page in reader.pages:
                    extracted = sanitize_text_for_db(page.extract_text() or "").strip()
                    if not extracted:
                        continue
                    remaining = AUTO_TAG_MAX_TEXT_CHARS - current_len
                    if remaining <= 0:
                        break
                    snippet = extracted[:remaining]
                    collected.append(snippet)
                    current_len += len(snippet)
                    if current_len >= AUTO_TAG_MAX_TEXT_CHARS:
                        break
                if collected:
                    return " ".join(" ".join(collected).split()).strip()
            except Exception:
                continue
        return ""

    def _normalize_display_name(self, raw_display_name: str) -> str:
        display_name = " ".join((raw_display_name or "").split()).strip()
        if not display_name:
            raise BadRequestError("Display name must not be empty")

        if any(separator in display_name for separator in ("/", "\\", ":")):
            raise BadRequestError("Display name contains invalid characters")

        if re.fullmatch(r"\.+", display_name):
            raise BadRequestError("Display name is invalid")

        if not display_name.lower().endswith(".pdf"):
            display_name = f"{display_name}.pdf"

        if len(display_name) > 200:
            raise BadRequestError("Display name is too long", details={"max_length": 200})

        return display_name

    def _storage_root(self) -> Path:
        return self.storage.storage_root

    def _resolve_storage_path(self, storage_key: str) -> Path:
        return self.storage.resolve_path(storage_key)

    def _relative_file_key(self, document_id: uuid.UUID, filename: str) -> str:
        return self.storage.relative_file_key(document_id, filename)

    def _cleanup_file(self, path: Path) -> None:
        self.storage.cleanup_file(path)

    def _validate_upload_file(self, file: UploadFile) -> str:
        return self.storage.validate_upload_file(file)

    def _inspect_upload_file(self, file: UploadFile) -> tuple[str, int]:
        return self.storage.inspect_upload_file(file)

    def _find_existing_document_by_sha256(self, file_sha256: str) -> uuid.UUID | None:
        return self.db.execute(
            self._scope(select(Document.id).where(Document.file_sha256 == file_sha256))
        ).scalar_one_or_none()

    def _store_pdf(self, file: UploadFile, destination: Path) -> int:
        return self.storage.store_pdf(file, destination)

    def _create_thumbnail(self, document_id: uuid.UUID, original_path: Path) -> tuple[str, int, str] | None:
        return self.storage.create_thumbnail(document_id, original_path)

    def _extract_quick_text_sample(self, pdf_path: Path) -> tuple[str, int, int, int]:
        return self.storage.extract_quick_text_sample(pdf_path)

    def _has_active_job(self, document_id: uuid.UUID, job_type: str) -> bool:
        return self.job_lifecycle.has_active(document_id, job_type)

    def _queue_index_job(self, document: Document, *, reason: str) -> bool:
        if not self.job_lifecycle.queue_index(document):
            return False
        logger.info("index job queued document_id=%s reason=%s", document.id, reason)
        return True

    def _queue_tag_job(self, document: Document, *, reason: str) -> bool:
        if not self.job_lifecycle.queue_tag(document):
            return False
        logger.info("tag job queued document_id=%s reason=%s", document.id, reason)
        return True

    def _queue_ocr_job(self, document: Document) -> Job:
        return self.job_lifecycle.queue_ocr(document)

    def queue_ocr_for_document(self, document_id: uuid.UUID) -> Document:
        document = self.get_document_or_404(document_id)
        try:
            self._get_file_record_by_role(document, DocumentFileRole.original)
        except NotFoundError as exc:
            raise ConflictError(
                "OCR cannot be started because the original PDF is missing",
                details={"document_id": str(document_id)},
            ) from exc

        self._queue_ocr_job(document)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc, "uq_jobs_document_type_active"):
                raise ConflictError(
                    "OCR job is already queued or running for this document",
                    details={"document_id": str(document_id)},
                ) from exc
            raise
        updated = self.get_document_or_404(document_id)
        logger.info("ocr job queued document_id=%s", document_id)
        return updated

    def backfill_ocr(
        self,
        *,
        limit: int,
        include_failed: bool = True,
        max_retries: int = 3,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Schließt OCR-Lücken: reiht OCR-Jobs für nicht gelöschte Dokumente
        ohne OCR ein (``ocr_status='not_started'``, optional ``'failed'`` bis
        ``max_retries``). Übersprungen werden Dokumente mit aktivem OCR-Job,
        ohne Original-PDF oder mit erschöpftem Retry-Limit. Pro Aufruf werden
        höchstens ``limit`` neue Jobs erstellt. Gibt eine Zusammenfassung zurück.
        """
        target_statuses = [DocumentOCRStatus.not_started.value]
        if include_failed:
            target_statuses.append(DocumentOCRStatus.failed.value)

        stmt = (
            select(Document)
            .where(
                Document.is_deleted.is_(False),
                Document.ocr_status.in_(target_statuses),
            )
            .order_by(Document.created_at.asc())
        )
        candidates = self.db.execute(stmt).scalars().all()

        queued_ids: list[str] = []
        skipped_active = 0
        skipped_retry_limit = 0
        skipped_missing_file = 0
        skipped_blocked = 0

        for document in candidates:
            if len(queued_ids) >= limit:
                break
            # Vom Nutzer per "Fehler entfernen" stillgelegte Dokumente nicht erneut einreihen.
            if (document.flags or {}).get("ocr_retry_blocked"):
                skipped_blocked += 1
                continue
            if self._has_active_job(document.id, "OCR"):
                skipped_active += 1
                continue
            if document.ocr_status == DocumentOCRStatus.failed.value and max_retries > 0:
                failed_count = self.db.execute(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.document_id == document.id,
                        Job.type == "OCR",
                        Job.status == "failed",
                    )
                ).scalar_one()
                if failed_count >= max_retries:
                    skipped_retry_limit += 1
                    continue
            try:
                self._get_file_record_by_role(document, DocumentFileRole.original)
            except NotFoundError:
                skipped_missing_file += 1
                continue
            if not dry_run:
                self._queue_ocr_job(document)
            queued_ids.append(str(document.id))

        if not dry_run and queued_ids:
            self.db.commit()
            logger.info("ocr backfill queued count=%s", len(queued_ids))

        return {
            "matched": len(candidates),
            "queued": len(queued_ids),
            "queued_document_ids": queued_ids,
            "skipped_active": skipped_active,
            "skipped_retry_limit": skipped_retry_limit,
            "skipped_missing_file": skipped_missing_file,
            "skipped_blocked": skipped_blocked,
            "limit": limit,
            "include_failed": include_failed,
            "dry_run": dry_run,
        }

    def queue_index_for_document(self, document_id: uuid.UUID, *, force: bool = False) -> Document:
        document = self.get_document_or_404(document_id)
        has_source = any(file_record.role in {DocumentFileRole.original.value, DocumentFileRole.ocr.value} for file_record in document.files)
        if not has_source and document.storage_key is None:
            raise ConflictError(
                "Indexing cannot be started because no source PDF is available",
                details={"document_id": str(document_id)},
            )

        if self._has_active_job(document.id, "INDEX"):
            raise ConflictError(
                "INDEX job is already queued or running for this document",
                details={"document_id": str(document_id)},
            )

        if force:
            document.text_hash = None

        self._queue_index_job(document, reason="manual_request")
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if is_unique_violation(exc, "uq_jobs_document_type_active"):
                raise ConflictError(
                    "INDEX job is already queued or running for this document",
                    details={"document_id": str(document_id)},
                ) from exc
            raise
        updated = self.get_document_or_404(document_id)
        logger.info("index job queued document_id=%s", document_id)
        return updated

    def auto_tag_document(self, document_id: uuid.UUID) -> Document:
        document = self.get_document_or_404(document_id)
        text_value = self._extract_text_for_manual_auto_tagging(document)
        if not text_value:
            raise ConflictError(
                "Tagging nicht möglich, weil kein extrahierbarer Text verfügbar ist.",
                details={"document_id": str(document_id)},
            )

        suggested_candidates = self._suggest_auto_tags_with_ai(text_value, max_tags=AUTO_TAG_MAX_SUGGESTIONS)
        if not suggested_candidates:
            logger.info("manual auto-tag no candidates document_id=%s", document_id)
            return document

        all_existing_tags = self.db.execute(
            self._scope_tags(select(Tag).order_by(func.lower(Tag.name).asc()))
        ).scalars().all()
        matched_existing_tags = self._resolve_existing_tags_for_candidates(suggested_candidates, all_existing_tags)

        current_tag_ids = {tag.id for tag in document.tags}
        applied_names: list[str] = []
        created_count = 0

        if matched_existing_tags:
            for tag in matched_existing_tags:
                if tag.id not in current_tag_ids:
                    document.tags.append(tag)
                    current_tag_ids.add(tag.id)
                applied_names.append(tag.name)
        else:
            # Only if no existing tag matches at all, create at most one new tag.
            created_tag, created = self._get_or_create_tag_case_insensitive(suggested_candidates[0])
            if created_tag is not None:
                if created_tag.id not in current_tag_ids:
                    document.tags.append(created_tag)
                    current_tag_ids.add(created_tag.id)
                applied_names.append(created_tag.name)
                created_count = 1 if created else 0

        self.db.commit()
        updated = self.get_document_or_404(document_id)
        logger.info(
            "manual auto-tag completed document_id=%s candidates=%s matched_existing=%s applied=%s created=%s",
            document_id,
            suggested_candidates,
            [tag.name for tag in matched_existing_tags],
            applied_names,
            created_count,
        )
        return updated

    def _build_ai_title(self, document: Document) -> str | None:
        """Build a human-readable title from stored classification fields."""
        doc_type = " ".join(str(document.ai_document_type or "").split()).strip()
        sender = " ".join(str(document.ai_sender or "").split()).strip()
        parts = [part for part in (doc_type, sender) if part]
        if not parts:
            return None
        title = " – ".join(parts)
        if document.ai_amount is not None:
            amount = f"{float(document.ai_amount):.2f}".replace(".", ",")
            currency = " ".join(str(document.ai_currency or "").split()).strip()
            suffix = f"{amount}€" if not currency or currency.upper() in {"EUR", "€"} else f"{amount} {currency}"
            title = f"{title} – {suffix}"
        return title[:200]

    def _suggest_document_type_from_classification(self, document: Document) -> str | None:
        """Den erkannten Dokumenttyp gegen die verwaltete Liste prüfen.

        ``ai_document_type`` ist bereits der feine Typ (z. B. "Kündigung"). Kein
        Legacy-Mapping mehr auf grobe Kategorien ("Verträge"). Liefert die
        kanonische Schreibweise des Typs, falls er ein bekannter Dokumenttyp ist,
        sonst ``None``.
        """
        raw = " ".join(str(document.ai_document_type or "").split()).strip()
        if not raw:
            return None
        type_stmt = select(DocumentType.name).where(func.lower(DocumentType.name) == raw.lower())
        if self.owner_id is not None:
            type_stmt = type_stmt.where(DocumentType.owner_id == self.owner_id)
        return self.db.execute(type_stmt).scalar_one_or_none()

    def _suggest_tags_from_classification(self, document: Document) -> list[str]:
        """Normalize the stored AI tags, preferring the casing of existing tags."""
        raw_tags = document.ai_suggested_tags or []
        if not raw_tags:
            return []
        existing_by_lower = {
            tag.name.lower(): tag.name
            for tag in self.db.execute(self._scope_tags(select(Tag))).scalars().all()
        }
        result: list[str] = []
        seen: set[str] = set()
        for raw in raw_tags:
            name = " ".join(str(raw or "").split()).strip()
            if not name:
                continue
            canonical = existing_by_lower.get(name.lower(), name)
            if canonical.lower() in seen:
                continue
            seen.add(canonical.lower())
            result.append(canonical)
        return result

    def suggest_metadata(self, document_id: uuid.UUID) -> DocumentMetadataSuggestion:
        """Return AI-derived suggestions for a document's editable fields.

        Reuses the stored classification when available; otherwise runs the
        Ollama classifier on demand (persisting the result), so the suggestions
        stay consistent with what the OCR worker produces.
        """
        document = self.get_document_or_404(document_id)

        if document.ai_status != "done":
            text_value = self._extract_text_for_manual_auto_tagging(document)
            if text_value:
                runtime_settings = SettingsService(self.db).get_settings().model_dump(mode="json")
                ollama_cfg = runtime_settings.get("ollama") or {}
                if not ollama_cfg.get("enabled"):
                    raise APIError(
                        status.HTTP_409_CONFLICT,
                        "AI_METADATA_DISABLED",
                        "KI-Metadaten sind in den Einstellungen deaktiviert.",
                    )
                doc_type_vocab = load_active_document_type_vocab(self.db)
                classification_warning = apply_ollama_classification(
                    document,
                    extracted_text=text_value,
                    quality_status=document.ocr_quality_status or "good",
                    confidence_score=document.ocr_confidence_score,
                    base_url=str(ollama_cfg.get("base_url") or "http://localhost:11434"),
                    model=str(ollama_cfg.get("model") or "llama3.2:3b"),
                    timeout_seconds=float(ollama_cfg.get("timeout_seconds") or 90.0),
                    allowed_document_types=document_type_names(doc_type_vocab),
                    document_type_hints=document_type_hint_map(doc_type_vocab),
                )
                self.db.commit()
                document = self.get_document_or_404(document_id)
                if classification_warning:
                    if document.ai_status == "error":
                        raise APIError(
                            status.HTTP_503_SERVICE_UNAVAILABLE,
                            "AI_METADATA_UNAVAILABLE",
                            classification_warning,
                        )
                    raise APIError(
                        status.HTTP_409_CONFLICT,
                        "AI_METADATA_SKIPPED",
                        classification_warning,
                    )
            else:
                raise APIError(
                    status.HTTP_409_CONFLICT,
                    "AI_METADATA_NO_TEXT",
                    "Kein OCR-Text für automatische KI-Metadaten verfügbar.",
                )

        correspondent = self._suggest_correspondent_from_classification(document)
        return DocumentMetadataSuggestion(
            display_name=self._build_ai_title(document),
            document_date=document.ai_document_date,
            document_type=self._suggest_document_type_from_classification(document),
            category=self._suggest_document_type_from_classification(document),
            correspondent_id=uuid.UUID(str(correspondent.correspondent_id)) if correspondent else None,
            correspondent_name=correspondent.name if correspondent else None,
            notes=" ".join(str(document.ai_summary or "").split()).strip() or None,
            tags=self._suggest_tags_from_classification(document),
        )

    def _suggest_correspondent_from_classification(self, document: Document):
        """Resolve the AI sender/OCR text to a known correspondent, best effort."""
        sender = " ".join(str(document.ai_sender or "").split()).strip()
        text_value = self._extract_text_for_manual_auto_tagging(document)
        if not sender and not text_value:
            return None
        try:
            return CorrespondentMatchingService(self.db, self.owner_id).resolve(
                sender=sender,
                filename=document.display_name or document.original_filename,
                ocr_text=text_value,
            )
        except Exception as exc:  # noqa: BLE001 - Korrespondenten-Vorschlag darf KI-Metadaten nicht blockieren
            logger.warning("metadata suggestion: correspondent matching failed document_id=%s error=%s", document.id, exc)
            return None

    def upload_document(
        self,
        file: UploadFile,
        document_date: date | None,
        notes: str | None,
        *,
        queue_processing: bool = True,
        scan_cleanup_applied: bool = False,
        scan_cleanup_mode: str | None = None,
    ) -> Document:
        runtime_settings = SettingsService(self.db).get_settings()
        auto_ocr_enabled = bool(runtime_settings.documents.auto_ocr)
        auto_tagging_enabled = bool(runtime_settings.documents.auto_tagging)
        has_explicit_document_date = document_date is not None

        original_filename = self._validate_upload_file(file)
        file_sha256, file_size_bytes = self._inspect_upload_file(file)

        existing_document_id = self._find_existing_document_by_sha256(file_sha256)
        if existing_document_id is not None:
            logger.info(
                "duplicate_exact_hit sha=%s existing_doc_id=%s original_filename=%s",
                file_sha256,
                existing_document_id,
                original_filename,
            )
            raise DuplicateExactError(
                "Dokument ist bereits vorhanden.",
                details={
                    "error": "duplicate_exact",
                    "existing_doc_id": str(existing_document_id),
                    "file_sha256": file_sha256,
                },
            )

        document = Document(
            owner_id=self.owner_id,
            original_filename=original_filename,
            document_date=document_date,
            document_date_source=(
                DocumentDateSource.manual.value if has_explicit_document_date else DocumentDateSource.pdf_meta.value
            ),
            notes=notes,
            status=DocumentStatus.imported.value,
            ocr_status=DocumentOCRStatus.not_started.value,
            text_source=DocumentTextSource.none.value,
            is_unread=True,
            mime_type="application/pdf",
            file_sha256=file_sha256,
            file_size_bytes=file_size_bytes,
            flags=(
                {
                    "scan_cleanup": {
                        "applied": True,
                        "source": "import_staging",
                        "mode": str(scan_cleanup_mode or "").strip(),
                    }
                }
                if scan_cleanup_applied
                else None
            ),
        )
        self.db.add(document)

        cleanup_paths: list[Path] = []
        stored_file_size = 0

        try:
            self.db.flush()

            if not has_explicit_document_date and document.document_date is None:
                created_reference = document.created_at or datetime.now(timezone.utc)
                document.document_date = created_reference.date()
                document.document_date_source = DocumentDateSource.pdf_meta.value

            original_key = self._relative_file_key(document.id, "original.pdf")
            original_path = self._resolve_storage_path(original_key)
            stored_file_size = self._store_pdf(file, original_path)
            cleanup_paths.append(original_path)

            original_file = DocumentFile(
                document_id=document.id,
                role=DocumentFileRole.original.value,
                file_key=original_key,
                filename="original.pdf",
                mime_type="application/pdf",
                bytes=stored_file_size,
            )
            self.db.add(original_file)

            document.storage_key = original_key
            document.file_size_bytes = stored_file_size

            thumbnail_result = self._create_thumbnail(document.id, original_path)
            if thumbnail_result is not None:
                thumbnail_key, thumbnail_size, thumbnail_mime = thumbnail_result
                thumbnail_path = self._resolve_storage_path(thumbnail_key)
                cleanup_paths.append(thumbnail_path)
                self.db.add(
                    DocumentFile(
                        document_id=document.id,
                        role=DocumentFileRole.thumbnail.value,
                        file_key=thumbnail_key,
                        filename="thumbnail.png",
                        mime_type=thumbnail_mime,
                        bytes=thumbnail_size,
                    )
                )

            try:
                quick_text_sample, non_whitespace_chars, pages_scanned, total_pages = self._extract_quick_text_sample(
                    original_path
                )
                document.page_count = total_pages
                is_textful_pdf = non_whitespace_chars >= settings.min_text_chars
                logger.info(
                    "upload text check document_id=%s chars=%s threshold=%s textful=%s scanned_pages=%s auto_ocr=%s auto_tagging=%s",
                    document.id,
                    non_whitespace_chars,
                    settings.min_text_chars,
                    is_textful_pdf,
                    pages_scanned,
                    auto_ocr_enabled,
                    auto_tagging_enabled,
                )

                if not queue_processing:
                    # Metadaten-only (z. B. Altbestand-Massenimport): Dokument anlegen,
                    # aber KEINE OCR-/Index-/Tag-Jobs starten. Auf schwacher Hardware
                    # (Raspberry Pi) würden sonst hunderte schwere Jobs gleichzeitig
                    # laufen. Volltext lässt sich später per "OCR-Lücken schließen"
                    # kontrolliert nachziehen.
                    document.status = DocumentStatus.ready.value
                    document.ocr_status = DocumentOCRStatus.not_started.value
                    if is_textful_pdf:
                        document.text_source = DocumentTextSource.embedded.value
                        document.text_content = quick_text_sample or None
                elif auto_ocr_enabled:
                    # Beim Import IMMER OCR durchführen – unabhängig davon, ob das PDF
                    # bereits eine eingebettete Textebene hat. (Gewünschtes Verhalten;
                    # gegated am auto_ocr-Schalter.) INDEX/TAG werden vom Worker nach
                    # Abschluss des OCR-Jobs nachgezogen.
                    self._queue_ocr_job(document)
                elif is_textful_pdf:
                    # auto_ocr aus: vorhandene Textebene verwenden, kein OCR.
                    document.status = DocumentStatus.ready.value
                    document.ocr_status = DocumentOCRStatus.not_started.value
                    document.ocr_quality_status = None
                    document.ocr_confidence_score = None
                    document.ocr_quality_message = None
                    document.ocr_processing_seconds = None
                    document.text_source = DocumentTextSource.embedded.value
                    document.text_content = quick_text_sample or None
                    if settings.index_auto_on_ready:
                        self._queue_index_job(document, reason="upload_textful")
                    elif auto_tagging_enabled:
                        self._queue_tag_job(document, reason="upload_textful_direct")
            except Exception as exc:
                logger.warning("upload text check failed document_id=%s error=%s", document.id, exc)
                if auto_ocr_enabled and queue_processing:
                    self._queue_ocr_job(document)

            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                for path in cleanup_paths:
                    self._cleanup_file(path)
                diag = getattr(getattr(exc, "orig", None), "diag", None)
                constraint_name = getattr(diag, "constraint_name", None)
                sqlstate = getattr(exc.orig, "sqlstate", None) if getattr(exc, "orig", None) is not None else None
                error_text = str(exc.orig) if exc.orig is not None else str(exc)
                winner_id = self._find_existing_document_by_sha256(file_sha256)
                if (
                    constraint_name == "uq_documents_file_sha256_not_null"
                    or "uq_documents_file_sha256_not_null" in error_text
                    or (sqlstate == "23505" and winner_id is not None)
                ):
                    logger.info(
                        "duplicate_exact_race sha=%s existing_doc_id=%s original_filename=%s constraint=%s sqlstate=%s",
                        file_sha256,
                        winner_id,
                        original_filename,
                        constraint_name,
                        sqlstate,
                    )
                    raise DuplicateExactError(
                        "Dokument ist bereits vorhanden.",
                        details={
                            "error": "duplicate_exact",
                            "existing_doc_id": str(winner_id) if winner_id else None,
                            "file_sha256": file_sha256,
                        },
                    ) from exc
                raise StorageError(
                    "Failed to persist document metadata",
                    details={
                        "constraint": constraint_name,
                        "sqlstate": sqlstate,
                        "error": error_text,
                    },
                ) from exc
            except Exception as exc:
                self.db.rollback()
                for path in cleanup_paths:
                    self._cleanup_file(path)
                raise StorageError("Failed to persist document metadata", details=str(exc)) from exc

            self.db.refresh(document)
            logger.info(
                "document uploaded id=%s original_filename=%s file_size=%s mime_type=%s sha=%s",
                document.id,
                original_filename,
                stored_file_size,
                file.content_type,
                file_sha256,
            )
            return document
        except (BadRequestError, PayloadTooLargeError, StorageError, DuplicateExactError):
            self.db.rollback()
            for path in cleanup_paths:
                self._cleanup_file(path)
            raise
        except Exception as exc:
            self.db.rollback()
            for path in cleanup_paths:
                self._cleanup_file(path)
            raise StorageError("Upload failed", details=str(exc)) from exc

    def _get_file_record_by_role(self, document: Document, role: DocumentFileRole) -> DocumentFile:
        for file_record in document.files:
            if file_record.role == role.value:
                return file_record

        # fallback for legacy records that only have storage_key
        if role == DocumentFileRole.original and document.storage_key:
            return DocumentFile(
                document_id=document.id,
                role=DocumentFileRole.original.value,
                file_key=document.storage_key,
                filename="original.pdf",
                mime_type=document.mime_type or "application/pdf",
            )

        raise NotFoundError(
            "Requested document file role not found",
            details={"document_id": str(document.id), "role": role.value},
        )

    def get_document_file_by_role(self, document_id: uuid.UUID, role: DocumentFileRole) -> tuple[Document, DocumentFile, Path]:
        stmt = self._scope(
            select(Document)
            .where(Document.id == document_id)
            .options(
                load_only(
                    Document.id,
                    Document.original_filename,
                    Document.storage_key,
                    Document.mime_type,
                ),
                selectinload(Document.files),
                noload(Document.tags),
                noload(Document.jobs),
                noload(Document.chunks),
            )
        )
        document = self.db.execute(stmt).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        file_record = self._get_file_record_by_role(document, role)
        file_path = self._resolve_storage_path(file_record.file_key)

        if not file_path.exists() or not file_path.is_file():
            logger.error(
                "document file missing document_id=%s role=%s file_key=%s",
                document_id,
                role.value,
                file_record.file_key,
            )
            raise NotFoundError(
                "Stored file was not found",
                details={"document_id": str(document_id), "role": role.value},
            )

        return document, file_record, file_path

    def _apply_filters(
        self,
        stmt,
        tag: str | None,
        tag_ids: list[uuid.UUID] | None,
        untagged: bool,
        status: DocumentStatus | None,
        date_from: date | None,
        date_to: date | None,
        recent_imports: bool,
        in_trash: bool = False,
        favorites_only: bool = False,
        without_text: bool = False,
        document_type: str | None = None,
        attention: DocumentAttentionFilter | None = None,
    ):
        return self.query._apply_filters(
            stmt, tag, tag_ids, untagged, status, date_from, date_to, recent_imports,
            in_trash=in_trash, favorites_only=favorites_only, without_text=without_text,
            document_type=document_type, attention=attention,
        )

    def _apply_attention_filter(self, stmt, attention: DocumentAttentionFilter):
        return self.query._apply_attention_filter(stmt, attention)

    def _normalize_search_query(self, q: str | None) -> str | None:
        from app.services.document_search import normalize_search_query

        return normalize_search_query(q, max_length=settings.search_query_max_length)

    def _build_ts_query_expr(self, normalized_query: str, fts_config: str):
        from app.services.document_search import build_ts_query_expr

        return build_ts_query_expr(normalized_query, fts_config)

    def _build_scoped_search_filter(self, normalized_query: str, search_scope: DocumentSearchScope):
        from app.services.document_search import build_scoped_search_filter

        return build_scoped_search_filter(normalized_query, search_scope)

    def list_documents(
        self,
        q: str | None,
        tag: str | None,
        tag_ids: list[uuid.UUID] | None,
        untagged: bool,
        status: DocumentStatus | None,
        date_from: date | None,
        date_to: date | None,
        recent_imports: bool,
        sort: DocumentSortField,
        order: SortOrder,
        limit: int,
        offset: int,
        include_total: bool = True,
        in_trash: bool = False,
        favorites_only: bool = False,
        without_text: bool = False,
        document_type: str | None = None,
        correspondent_id: uuid.UUID | None = None,
        search_scope: DocumentSearchScope = DocumentSearchScope.all,
        attention: DocumentAttentionFilter | None = None,
    ) -> DocumentListResponse:
        return self.query.list_documents(
            q, tag, tag_ids, untagged, status, date_from, date_to, recent_imports, sort, order, limit, offset,
            include_total, in_trash, favorites_only, without_text, document_type, search_scope, attention,
            correspondent_id=correspondent_id,
        )

    def calendar_counts(self, **kwargs):
        return self.query.calendar_counts(**kwargs)

    def get_document_statuses(self, document_ids: list[uuid.UUID]) -> DocumentStatusListResponse:
        return self.query.statuses(document_ids)

    def create_document(self, payload: DocumentCreateRequest) -> Document:
        document = Document(
            owner_id=self.owner_id,
            original_filename=payload.original_filename.strip(),
            document_date=payload.document_date,
            notes=payload.notes,
            status=DocumentStatus.imported.value,
            ocr_status=DocumentOCRStatus.not_started.value,
            text_source=DocumentTextSource.none.value,
            is_unread=True,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        logger.info("document created id=%s", document.id)
        return document

    def get_document_or_404(self, document_id: uuid.UUID) -> Document:
        stmt = self._scope(
            select(Document)
            .where(Document.id == document_id)
            .options(
                selectinload(Document.tags),
                selectinload(Document.files),
                selectinload(Document.jobs),
                noload(Document.chunks),
            )
        )
        document = self.db.execute(stmt).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        return document

    def update_document(self, document_id: uuid.UUID, payload: DocumentUpdateRequest) -> Document:
        document = self.get_document_or_404(document_id)
        data = payload.model_dump(exclude_unset=True)

        if "document_date" in data:
            document.document_date = data["document_date"]
            document.document_date_source = "manual"
            document.document_date_confidence = None
            document.document_date_candidates = None
            retention = self.db.execute(
                select(DocumentRetention).where(DocumentRetention.document_id == document_id)
            ).scalar_one_or_none()
            if retention is not None:
                retention.retain_until = _compute_retain_until(
                    data["document_date"],
                    retention.period_years,
                )
                retention.updated_at = datetime.now(timezone.utc)
        if "notes" in data:
            document.notes = data["notes"]
        if "document_type" in data:
            document.document_type = data["document_type"]
        if "correspondent_id" in data:
            correspondent_id = data["correspondent_id"]
            if correspondent_id is not None:
                correspondent = self.db.get(Correspondent, correspondent_id)
                if correspondent is None or (
                    self.owner_id is not None and correspondent.owner_id != self.owner_id
                ):
                    raise BadRequestError(
                        "Correspondent not found",
                        details={"correspondent_id": str(correspondent_id)},
                    )
            document.correspondent_id = correspondent_id
        if "status" in data and data["status"] is not None:
            document.status = data["status"].value
        if "display_name" in data:
            document.display_name = (
                None if data["display_name"] is None else self._normalize_display_name(data["display_name"])
            )

        self.db.commit()
        updated = self.get_document_or_404(document_id)
        logger.info("document updated id=%s", document_id)
        return updated

    def mark_document_viewed(self, document_id: uuid.UUID) -> bool:
        document = self.get_document_or_404(document_id)
        if not document.is_unread:
            return False

        document.is_unread = False
        self.db.commit()
        logger.info("document marked viewed id=%s", document_id)
        return True

    def trash_document(self, document_id: uuid.UUID) -> Document:
        """Soft-Delete: Dokument in den Papierkorb verschieben."""
        document = self.get_document_or_404(document_id)
        document.is_deleted = True
        document.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(document)
        logger.info("document trashed id=%s", document_id)
        return document

    def restore_document(self, document_id: uuid.UUID) -> Document:
        """Dokument aus dem Papierkorb wiederherstellen."""
        # get_document_or_404 filtert is_deleted=True heraus – direkt abfragen
        from sqlalchemy import select as sa_select
        document = self.db.scalar(self._scope(sa_select(Document).where(Document.id == document_id)))
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        if not document.is_deleted:
            raise BadRequestError("Document is not in trash", details={"document_id": str(document_id)})
        document.is_deleted = False
        document.deleted_at = None
        self.db.commit()
        self.db.refresh(document)
        logger.info("document restored id=%s", document_id)
        return document

    def toggle_favorite(self, document_id: uuid.UUID) -> Document:
        """Favoriten-Status umschalten."""
        document = self.get_document_or_404(document_id)
        document.is_favorite = not document.is_favorite
        self.db.commit()
        self.db.refresh(document)
        logger.info("document favorite toggled id=%s is_favorite=%s", document_id, document.is_favorite)
        return document

    def delete_document(self, document_id: uuid.UUID) -> None:
        """Endgültiges Löschen – auch für Dokumente im Papierkorb."""
        # Auch gelöschte Dokumente permanent entfernen können
        from sqlalchemy import select as sa_select
        document = self.db.scalar(self._scope(sa_select(Document).where(Document.id == document_id)))
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        file_keys = {file_record.file_key for file_record in document.files}
        if document.storage_key:
            file_keys.add(document.storage_key)

        self.db.delete(document)
        self.db.commit()

        for file_key in file_keys:
            try:
                self._cleanup_file(self._resolve_storage_path(file_key))
            except StorageError:
                continue

        logger.info("document deleted id=%s", document_id)

    def empty_trash(self) -> int:
        """Endgültig alle Dokumente im Papierkorb löschen."""
        documents = list(
            self.db.execute(
                self._scope(
                    select(Document)
                    .where(Document.is_deleted.is_(True))
                    .options(selectinload(Document.files))
                )
            ).scalars()
        )
        if not documents:
            return 0

        file_keys: set[str] = set()
        for document in documents:
            file_keys.update(file_record.file_key for file_record in document.files)
            if document.storage_key:
                file_keys.add(document.storage_key)
            self.db.delete(document)

        self.db.commit()

        for file_key in file_keys:
            try:
                self._cleanup_file(self._resolve_storage_path(file_key))
            except StorageError:
                continue

        deleted_count = len(documents)
        logger.info("trash emptied deleted_count=%s", deleted_count)
        return deleted_count

    def purge_expired_trash(self, retention_days: int) -> int:
        """Endgültig löschen, was länger als retention_days im Papierkorb liegt."""
        retention_days = int(retention_days)
        if retention_days <= 0:
            return 0

        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        document_ids = self.db.scalars(
            select(Document.id)
            .where(Document.is_deleted.is_(True))
            .where(Document.deleted_at.is_not(None))
            .where(Document.deleted_at <= threshold)
            .order_by(Document.deleted_at.asc())
        ).all()

        deleted_count = 0
        for document_id in document_ids:
            try:
                self.delete_document(document_id)
                deleted_count += 1
            except Exception:
                self.db.rollback()
                logger.exception("expired trash document cleanup failed id=%s", document_id)

        if deleted_count:
            logger.info("expired trash cleanup deleted_count=%s retention_days=%s", deleted_count, retention_days)
        return deleted_count

    def replace_document_tags(self, document_id: uuid.UUID, payload: DocumentTagReplaceRequest) -> Document:
        document = self.get_document_or_404(document_id)
        old_tag_ids = {tag.id for tag in document.tags}
        old_count = len(document.tags)

        unique_tag_ids = list(dict.fromkeys(payload.tag_ids))
        if unique_tag_ids:
            tags_stmt = self._scope_tags(select(Tag).where(Tag.id.in_(unique_tag_ids)))
            tags = self.db.execute(tags_stmt).scalars().all()
            found_ids = {tag.id for tag in tags}
            missing_ids = [str(tag_id) for tag_id in unique_tag_ids if tag_id not in found_ids]
            if missing_ids:
                raise NotFoundError("One or more tags were not found", details={"missing_tag_ids": missing_ids})
        else:
            tags = []

        document.tags = tags
        self.db.commit()

        updated = self.get_document_or_404(document_id)
        logger.info(
            "document tags replaced document_id=%s old_count=%s new_count=%s",
            document_id,
            old_count,
            len(tags),
        )
        return updated

    def remove_document_tag(self, document_id: uuid.UUID, tag_id: uuid.UUID) -> Document:
        document = self.get_document_or_404(document_id)
        current_tag_ids = {tag.id for tag in document.tags}
        if tag_id not in current_tag_ids:
            raise NotFoundError(
                "Tag relation not found for document",
                details={"document_id": str(document_id), "tag_id": str(tag_id)},
            )

        document.tags = [tag for tag in document.tags if tag.id != tag_id]
        self.db.commit()

        updated = self.get_document_or_404(document_id)
        logger.info(
            "document tag removed document_id=%s tag_id=%s",
            document_id,
            tag_id,
        )
        return updated

    def as_detail(self, document: Document) -> DocumentDetail:
        detail = DocumentDetail.model_validate(document, from_attributes=True)
        detail.is_duplicate = document.duplicate_of_doc_id is not None
        if document.correspondent_id is not None:
            correspondent = self.db.get(Correspondent, document.correspondent_id)
            detail.correspondent_name = correspondent.name if correspondent is not None else None
        return detail

import logging
import json
import os
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from fastapi import UploadFile
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError, BadRequestError, ForbiddenError, PayloadTooLargeError, StorageError
from app.models.correspondent import Correspondent
from app.models.document import Document
from app.models.tag import Tag
from app.schemas.documents import DocumentTagReplaceRequest
from app.schemas.import_staging import (
    ImportCommitCreatedItem,
    ImportCommitErrorItem,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportSourceRead,
    ImportSourceUploadResponse,
)
from app.services.correspondent_matching import CorrespondentMatchingService
from app.services.document_types import (
    document_type_hint_map,
    document_type_names,
    load_active_document_type_vocab,
)
from app.services.documents import ALLOWED_PDF_CONTENT_TYPES, DocumentService
from app.services.import_timing import elapsed_ms, log_import_timing, now_perf
from app.services.import_metadata_rules import (
    AMOUNT_RE as _AMOUNT_RE,
    DATE_DMY_RE as _DATE_DMY_RE,
    DATE_YMD_RE as _DATE_YMD_RE,
    DOC_TYPES_ALLOWED as _DOC_TYPES_ALLOWED,
    detect_amount_currency,
    detect_document_type,
    detect_document_type_improved,
    extract_document_date,
    normalize_document_type,
)
from app.services.import_metadata_response import (
    coerce_llm_scalar,
    extract_json_object,
    extract_loose_fields,
    safe_float,
)
from app.services.import_metadata_heuristics import (
    detect_sender,
    detect_subject_heuristic,
    extract_issuer_from_line,
    extract_subject_rich,
    generate_tags_from_text,
    is_subject_supported_by_context,
    normalize_issuer,
    normalize_subject,
)
from app.services.import_ollama_prompt import build_naming_examples_block, select_staging_llm_text
from app.services.import_ollama_client import request_generation
from app.services.import_title_formatting import (
    build_fallback_title,
    build_filename_from_meta,
    build_note_from_metadata,
    format_euro,
    sanitize_title,
)
from app.services.naming_templates import NamingTemplateService
from app.services.ocr_pipeline import (
    build_bw_pdf,
    build_cleaned_scan_pdf,
    build_grayscale_pdf,
    detect_pdf_color_page_indices,
    normalize_scan_cleanup_mode,
    render_pdf_page_preview,
    render_pdf_page_color_preview,
    run_ocr_lite,
    run_ocr_pipeline,
)
from app.services.retention import DocumentRetentionService, evaluate_retention_suggestion
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.import_staging")
settings = get_settings()
_INVALID_TITLE_CHARS = re.compile(r'[\/\\:*?"<>|]+')
_WHITESPACE_RE = re.compile(r"\s+")
_FILENAME_SEPARATOR = " – "
_FILENAME_MAX_LEN = 80
_STAGING_MIN_TEXT_CHARS = 80
_STAGING_GOOD_TEXT_CHARS = 240
_STAGING_PREVIEW_MAX_LONG_EDGE = 640
_STAGING_ANALYSIS_CACHE_VERSION = 1
_STAGING_PREANALYSIS_STATE_VERSION = 1
_STAGING_SCAN_CLEANUP_CACHE_VERSION = 1
_STAGING_COLOR_PROFILE_CACHE_VERSION = 1
_STAGING_PREANALYSIS_MAX_AGE_SECONDS = 15 * 60
_OWNER_SENTINEL = object()
_STAGING_OCR_ATTEMPTS = (
    {"psm": 6, "max_long_side_px": 2800},
    {"psm": 4, "max_long_side_px": 3200},
    {"psm": 11, "max_long_side_px": 3200},
)
_LLM_SIGNAL_KEYWORDS = (
    "rechnung",
    "rechnungsnummer",
    "rechnungsnr",
    "invoice",
    "gesamtbetrag",
    "summe",
    "total",
    "betrag",
    "datum",
    "rechnungsdatum",
    "belegdatum",
    "kundennummer",
    "kunden-nr",
    "vertragsnummer",
    "aktenzeichen",
    "frist",
    "fällig",
    "faellig",
    "bescheid",
    "steuer",
    "versicherung",
    "kündigung",
    "kuendigung",
    "vertrag",
    "mahnung",
    "zahlbar",
)
_INVOICE_NO_RE = re.compile(
    r"\b(?:rechnungsnummer|rechnung\s*nr|invoice\s*no|belegnummer|belegnr|rg)\s*[:#-]?\s*([A-Z0-9-]{3,})\b",
    re.IGNORECASE,
)
_CUSTOMER_NO_RE = re.compile(
    r"\b(?:kundennummer|kunden[-\s]?nr|customer\s*id)\s*[:#-]?\s*([A-Z0-9-]{2,})\b",
    re.IGNORECASE,
)

class _LocalPdfUpload:
    def __init__(self, filename: str, source_path: Path) -> None:
        self.filename = filename
        self.content_type = "application/pdf"
        self.file = source_path.open("rb")

    def close(self) -> None:
        self.file.close()


class ImportStagingService:
    def __init__(self, db: Session, owner_id=None):
        self.db = db
        self.owner_id = owner_id
        self.document_service = DocumentService(db, owner_id)
        self.settings_service = SettingsService(db)

    def _staging_root(self) -> Path:
        storage_root = Path(settings.storage_path).resolve()
        return (storage_root / "import_staging").resolve()

    def _source_pdf_path(self, source_file_id: str) -> Path:
        source_id = str(source_file_id or "").strip()
        if not source_id:
            raise BadRequestError("source_file_id is missing")
        try:
            parsed = uuid.UUID(source_id)
        except ValueError as exc:
            raise BadRequestError("source_file_id is invalid", details={"source_file_id": source_id}) from exc
        return self._staging_root() / f"{parsed}.pdf"

    def _source_preview_path(self, source_file_id: str) -> Path:
        source_id = str(source_file_id or "").strip()
        if not source_id:
            raise BadRequestError("source_file_id is missing")
        try:
            parsed = uuid.UUID(source_id)
        except ValueError as exc:
            raise BadRequestError("source_file_id is invalid", details={"source_file_id": source_id}) from exc
        return self._staging_root() / f"{parsed}.preview.png"

    def _source_raw_pdf_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        return source_path.with_name(f"{source_path.stem}.raw.pdf")

    def _source_scan_cleanup_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        return source_path.with_name(f"{source_path.stem}.scan-cleanup.json")

    def _source_color_profile_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        return source_path.with_name(f"{source_path.stem}.color-profile.json")

    @staticmethod
    def _utc_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _source_file_signature(path: Path) -> dict[str, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }

    @staticmethod
    def _analysis_owner_key(owner_id) -> str:
        if owner_id is None:
            return "global"
        try:
            return str(uuid.UUID(str(owner_id)))
        except (TypeError, ValueError):
            return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(owner_id or "").strip()) or "global"

    def _source_analysis_path(self, source_file_id: str, owner_id=_OWNER_SENTINEL) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        owner_key = self._analysis_owner_key(self.owner_id if owner_id is _OWNER_SENTINEL else owner_id)
        return source_path.with_name(f"{source_path.stem}.analysis.{owner_key}.json")

    def _source_analysis_paths(self, source_file_id: str) -> list[Path]:
        source_path = self._source_pdf_path(source_file_id)
        return list(source_path.parent.glob(f"{source_path.stem}.analysis.*.json"))

    def _source_preanalysis_state_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        return source_path.with_name(f"{source_path.stem}.preanalysis.json")

    def mark_source_preanalysis_pending(self, source_file_ids: list[str]) -> None:
        """Advertise that the worker owns the expensive first analysis.

        Scanner imports arrive in the dialog before cleanup and OCR-lite finish.
        Without this shared marker, the API and worker start the same OCR in
        parallel; on the Pi that makes the browser timeout look like a failure.
        """
        for source_file_id in self._normalize_source_file_ids(source_file_ids):
            try:
                destination = self._source_preanalysis_state_path(source_file_id)
            except BadRequestError:
                continue
            payload = {
                "preanalysis_version": _STAGING_PREANALYSIS_STATE_VERSION,
                "source_file_id": source_file_id,
                "status": "pending",
                "updated_at": self._utc_timestamp(),
            }
            temp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                os.replace(temp_path, destination)
            except OSError as exc:
                temp_path.unlink(missing_ok=True)
                logger.warning("import source preanalysis marker write failed source_file_id=%s err=%s", source_file_id, exc)

    def clear_source_preanalysis_pending(self, source_file_id: str) -> None:
        try:
            self._source_preanalysis_state_path(source_file_id).unlink(missing_ok=True)
        except (BadRequestError, OSError):
            pass

    def is_source_preanalysis_pending(self, source_file_id: str) -> bool:
        try:
            path = self._source_preanalysis_state_path(source_file_id)
            stat = path.stat()
            if datetime.now(timezone.utc).timestamp() - stat.st_mtime > _STAGING_PREANALYSIS_MAX_AGE_SECONDS:
                return False
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (BadRequestError, OSError, ValueError, TypeError):
            return False
        return (
            isinstance(payload, dict)
            and int(payload.get("preanalysis_version") or 0) == _STAGING_PREANALYSIS_STATE_VERSION
            and str(payload.get("status") or "") == "pending"
        )

    @staticmethod
    def _source_analysis_response_payload(result: dict[str, object] | None) -> dict[str, object] | None:
        if not isinstance(result, dict):
            return None
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        return {
            "suggestion": str(result.get("suggestion") or "").strip(),
            "status": str(result.get("status") or "ready").strip() or "ready",
            "pageScope": str(result.get("page_scope") or result.get("pageScope") or "first_page"),
            "usedFallback": bool(result.get("used_fallback", result.get("usedFallback", False))),
            "meta": dict(meta or {}),
        }

    def get_source_analysis(self, source_file_id: str) -> dict[str, object] | None:
        try:
            paths = [self._source_analysis_path(source_file_id)]
            if self.owner_id is not None:
                paths.append(self._source_analysis_path(source_file_id, owner_id=None))
        except BadRequestError:
            return None
        for path in paths:
            try:
                if not path.exists() or not path.is_file():
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("import source analysis cache read failed path=%s err=%s", path, exc)
                continue
            if not isinstance(payload, dict):
                continue
            if int(payload.get("analysis_version") or 0) != _STAGING_ANALYSIS_CACHE_VERSION:
                continue
            result = payload.get("result")
            if isinstance(result, dict):
                return result
        return None

    def get_source_analysis_response(self, source_file_id: str) -> dict[str, object] | None:
        return self._source_analysis_response_payload(self.get_source_analysis(source_file_id))

    def store_source_analysis(
        self,
        source_file_id: str,
        result: dict[str, object],
        *,
        page_scope: str = "first_page",
        analysis_phase: str = "llm",
    ) -> dict[str, object]:
        if not isinstance(result, dict):
            raise BadRequestError("analysis result is invalid")
        normalized_scope = "all_pages" if str(page_scope or "").strip().lower() == "all_pages" else "first_page"
        cached_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        stored_result = dict(result)
        stored_meta = dict(stored_result.get("meta") or {})
        stored_meta.update({
            "analysis_phase": str(analysis_phase or "llm"),
            "cached_at": cached_at,
            "source_file_id": str(source_file_id),
        })
        stored_result["meta"] = stored_meta
        stored_result["page_scope"] = normalized_scope
        payload = {
            "analysis_version": _STAGING_ANALYSIS_CACHE_VERSION,
            "source_file_id": str(source_file_id),
            "owner_key": self._analysis_owner_key(self.owner_id),
            "page_scope": normalized_scope,
            "cached_at": cached_at,
            "result": stored_result,
        }
        destination = self._source_analysis_path(source_file_id)
        temp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(temp_path, destination)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise StorageError("Could not store import source analysis") from exc
        return stored_result

    def _delete_source_analyses(self, source_file_id: str) -> None:
        try:
            paths = self._source_analysis_paths(source_file_id)
        except BadRequestError:
            return
        for path in paths:
            path.unlink(missing_ok=True)

    def _read_source_scan_cleanup(self, source_file_id: str) -> dict[str, object] | None:
        try:
            path = self._source_scan_cleanup_path(source_file_id)
        except BadRequestError:
            return None
        try:
            if not path.exists() or not path.is_file():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("import source scan cleanup cache read failed path=%s err=%s", path, exc)
            return None
        if not isinstance(payload, dict):
            return None
        if int(payload.get("cleanup_version") or 0) != _STAGING_SCAN_CLEANUP_CACHE_VERSION:
            return None
        return payload

    def get_source_scan_cleanup_response(self, source_file_id: str) -> dict[str, object] | None:
        payload = self._read_source_scan_cleanup(source_file_id)
        if not isinstance(payload, dict):
            return None
        status = str(payload.get("status") or "").strip()
        if not status:
            return None
        response: dict[str, object] = {
            "status": status,
            "mode": str(payload.get("mode") or "").strip(),
            "updated_at": str(payload.get("updated_at") or "").strip(),
        }
        for key in ("started_at", "completed_at", "duration_ms", "revision", "message"):
            value = payload.get(key)
            if value not in (None, ""):
                response[key] = value
        return response

    def _write_source_scan_cleanup(
        self,
        source_file_id: str,
        *,
        status: str,
        mode: str,
        **extra: object,
    ) -> dict[str, object]:
        destination = self._source_scan_cleanup_path(source_file_id)
        payload: dict[str, object] = {
            "cleanup_version": _STAGING_SCAN_CLEANUP_CACHE_VERSION,
            "source_file_id": str(source_file_id),
            "status": str(status or "").strip() or "unknown",
            "mode": str(mode or "").strip(),
            "updated_at": self._utc_timestamp(),
            **extra,
        }
        temp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(temp_path, destination)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            logger.warning("import source scan cleanup cache write failed source_file_id=%s err=%s", source_file_id, exc)
        return payload

    def _delete_source_scan_cleanup_artifacts(self, source_file_id: str) -> None:
        try:
            source_path = self._source_pdf_path(source_file_id)
            raw_path = self._source_raw_pdf_path(source_file_id)
            cleanup_path = self._source_scan_cleanup_path(source_file_id)
        except BadRequestError:
            return
        raw_path.unlink(missing_ok=True)
        cleanup_path.unlink(missing_ok=True)
        self.clear_source_preanalysis_pending(source_file_id)
        self._source_color_profile_path(source_file_id).unlink(missing_ok=True)
        for temp_path in source_path.parent.glob(f"{source_path.stem}.scan-cleanup.*.tmp.pdf"):
            temp_path.unlink(missing_ok=True)

    def get_source_color_profile(self, source_file_id: str) -> dict[str, object]:
        """Gecachte Farbfähigkeit des unveränderten Scans, pro Seite."""
        raw_path = self._source_raw_pdf_path(source_file_id)
        source_path = raw_path if raw_path.exists() else self._source_pdf_path(source_file_id)
        signature = self._source_file_signature(source_path)
        if signature is None:
            return {"color_page_indices": [], "color_detection_available": False}
        profile_path = self._source_color_profile_path(source_file_id)
        try:
            cached = json.loads(profile_path.read_text(encoding="utf-8"))
            if (
                int(cached.get("version") or 0) == _STAGING_COLOR_PROFILE_CACHE_VERSION
                and cached.get("source_signature") == signature
            ):
                return {
                    "color_page_indices": [int(index) for index in cached.get("color_page_indices") or [] if int(index) >= 0],
                    "color_detection_available": bool(cached.get("color_detection_available", True)),
                }
        except (OSError, ValueError, TypeError):
            pass

        detected_indices = detect_pdf_color_page_indices(source_path)
        detection_available = detected_indices is not None
        color_page_indices = detected_indices or []
        payload = {
            "version": _STAGING_COLOR_PROFILE_CACHE_VERSION,
            "source_signature": signature,
            "color_page_indices": color_page_indices,
            "color_detection_available": detection_available,
        }
        temp_path = profile_path.with_name(f"{profile_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temp_path, profile_path)
        except OSError:
            temp_path.unlink(missing_ok=True)
        return {"color_page_indices": color_page_indices, "color_detection_available": detection_available}

    def get_source_color_page_indices(self, source_file_id: str) -> list[int]:
        return list(self.get_source_color_profile(source_file_id)["color_page_indices"])

    def _regenerate_source_preview(self, source_file_id: str, source_path: Path) -> None:
        """Vorschau-PNG aus der bereinigten PDF neu rendern.

        Das vom Host gelieferte PNG zeigt den Rohscan. Würde es nur gelöscht,
        bliebe preview_url dauerhaft leer und die Karte im Importfenster hätte
        bis zum fertigen Client-Rendering kein Bild mehr.
        """
        destination = self._source_preview_path(source_file_id)
        temp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
        rendered = render_pdf_page_preview(
            source_path,
            temp_path,
            max_long_edge=_STAGING_PREVIEW_MAX_LONG_EDGE,
        )
        if rendered is None:
            temp_path.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            return
        try:
            os.replace(temp_path, destination)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            logger.warning("import source preview refresh failed source_file_id=%s err=%s", source_file_id, exc)

    def source_preview_url(self, source_file_id: str) -> str | None:
        try:
            preview_path = self._source_preview_path(source_file_id)
        except BadRequestError:
            return None
        if not preview_path.exists() or not preview_path.is_file():
            return None
        return f"/api/import/source/{source_file_id}/preview"

    def get_source_preview_path(self, source_file_id: str) -> Path | None:
        preview_path = self._source_preview_path(source_file_id)
        if not preview_path.exists() or not preview_path.is_file():
            return None
        return preview_path

    def get_source_pdf_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        if not source_path.exists() or not source_path.is_file():
            raise BadRequestError("Staging source PDF not found", details={"source_file_id": source_file_id})
        return source_path

    def render_source_page_color_preview(self, source_file_id: str, page_index: int, mode: str) -> bytes | None:
        normalized_mode = str(mode or "auto").strip().lower()
        source_path = self._source_path_for_color_mode(source_file_id, normalized_mode)
        return render_pdf_page_color_preview(
            source_path,
            page_index=int(page_index),
            mode=normalized_mode,
        )

    def _validate_source_file(self, file: UploadFile) -> str:
        filename = (file.filename or "").strip()
        if not filename:
            raise BadRequestError("Filename is missing")
        if not filename.lower().endswith(".pdf"):
            raise BadRequestError("Only .pdf files are allowed")

        content_type = (file.content_type or "").lower()
        if content_type and content_type not in ALLOWED_PDF_CONTENT_TYPES:
            raise BadRequestError(
                "Only PDF content types are allowed",
                details={"content_type": file.content_type},
            )

        return filename

    def _store_source_pdf(self, file: UploadFile, destination: Path) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_name(f"{destination.name}.uploading")
        bytes_written = 0
        header_checked = False
        max_bytes = settings.upload_max_bytes

        try:
            file.file.seek(0)
            with temp_path.open("wb") as handle:
                while True:
                    chunk = file.file.read(1024 * 1024)
                    if not chunk:
                        break

                    if not header_checked:
                        if not chunk.startswith(b"%PDF-"):
                            raise BadRequestError("File content is not a valid PDF")
                        header_checked = True

                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise PayloadTooLargeError(
                            "Uploaded file exceeds maximum allowed size",
                            details={"max_bytes": max_bytes},
                        )

                    handle.write(chunk)

            if bytes_written == 0:
                raise BadRequestError("Uploaded file is empty")

            os.replace(temp_path, destination)
            return bytes_written
        except (BadRequestError, PayloadTooLargeError):
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise StorageError("Failed to write source PDF", details=str(exc)) from exc
        finally:
            file.file.seek(0)

    def store_source_preview(self, source_file_id: str, preview_path: Path | None) -> Path | None:
        preview_started = now_perf()
        if preview_path is None:
            log_import_timing(
                "preview_skipped",
                source_file_id=source_file_id,
                reason="no_preview_path",
                duration_ms=elapsed_ms(preview_started),
            )
            return None
        source_path = Path(preview_path)
        try:
            has_preview = source_path.exists() and source_path.is_file() and source_path.stat().st_size > 0
        except OSError:
            has_preview = False
        if not has_preview:
            log_import_timing(
                "preview_skipped",
                source_file_id=source_file_id,
                reason="empty_or_missing_preview",
                duration_ms=elapsed_ms(preview_started),
            )
            return None

        destination = self._source_preview_path(source_file_id)
        temp_path = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            with Image.open(source_path) as raw_image:
                image = ImageOps.exif_transpose(raw_image)
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")
                image.thumbnail((_STAGING_PREVIEW_MAX_LONG_EDGE, _STAGING_PREVIEW_MAX_LONG_EDGE))
                destination.parent.mkdir(parents=True, exist_ok=True)
                image.save(temp_path, format="PNG", optimize=True)
            os.replace(temp_path, destination)
            log_import_timing(
                "preview_stored",
                source_file_id=source_file_id,
                duration_ms=elapsed_ms(preview_started),
            )
            return destination
        except Exception as exc:  # noqa: BLE001 - Vorschau ist optional
            temp_path.unlink(missing_ok=True)
            logger.warning("import source preview skipped source_file_id=%s err=%s", source_file_id, exc)
            log_import_timing(
                "preview_skipped",
                source_file_id=source_file_id,
                reason="preview_store_failed",
                duration_ms=elapsed_ms(preview_started),
            )
            return None

    def _scan_cleanup_settings(self) -> tuple[str | None, int]:
        runtime_settings = self.settings_service.get_settings().model_dump(mode="json")
        ocr_settings = runtime_settings.get("ocr", {}) if isinstance(runtime_settings, dict) else {}
        mode = normalize_scan_cleanup_mode(ocr_settings.get("scan_cleanup"))
        try:
            dpi_target = max(300, int(ocr_settings.get("dpi_target") or 300))
        except (TypeError, ValueError):
            dpi_target = 300
        # Die Staging-Bereinigung erhält bewusst IMMER die Farbe (white): Ob das
        # importierte Dokument farbig oder grau wird, entscheidet die Auswahl im
        # Importdialog (Original / Bereinigt Graustufen / Bereinigt Farbe). Ein
        # persistiertes „bw" (Altwert) wird daher wie „white" behandelt, damit
        # „Bereinigt Farbe" verlässlich Farbe liefern kann.
        return ("white" if mode in {"white", "bw"} else None), dpi_target

    def mark_scan_cleanup_pending(self, source_file_ids: list[str]) -> bool:
        """Wartende Quellen sofort als "pending" markieren.

        Ohne das bekäme bei einer Charge nur die gerade laufende Quelle einen
        Status - die übrigen Karten zeigen bis zu ihrem eigenen Durchlauf keinen
        Spinner, obwohl die Bereinigung für sie bereits eingeplant ist.
        """
        mode, _ = self._scan_cleanup_settings()
        if mode is None:
            return False
        for source_file_id in source_file_ids:
            source_id = str(source_file_id or "").strip()
            if not source_id:
                continue
            self._write_source_scan_cleanup(source_id, status="pending", mode=mode)
        return True

    def enhance_source_scan(self, source_file_id: str) -> dict[str, object] | None:
        source_id = str(source_file_id or "").strip()
        if not source_id:
            return None

        mode, dpi_target = self._scan_cleanup_settings()
        if mode is None:
            return None

        cleanup_started = now_perf()
        source_path = self._source_pdf_path(source_id)
        if not source_path.exists() or not source_path.is_file():
            return self._write_source_scan_cleanup(
                source_id,
                status="failed",
                mode=mode,
                message="source_missing",
                duration_ms=elapsed_ms(cleanup_started),
            )

        initial_signature = self._source_file_signature(source_path)
        if initial_signature is None:
            return self._write_source_scan_cleanup(
                source_id,
                status="failed",
                mode=mode,
                message="source_unreadable",
                duration_ms=elapsed_ms(cleanup_started),
            )

        started_at = self._utc_timestamp()
        self._write_source_scan_cleanup(
            source_id,
            status="running",
            mode=mode,
            started_at=started_at,
            source_signature=initial_signature,
        )
        candidate_path = source_path.with_name(f"{source_path.stem}.scan-cleanup.{uuid.uuid4().hex}.tmp.pdf")
        produced_path: Path | None = None
        try:
            produced_path = build_cleaned_scan_pdf(
                source_path,
                candidate_path,
                mode=mode,
                dpi_target=dpi_target,
            )
            if produced_path is None or not produced_path.exists():
                return self._write_source_scan_cleanup(
                    source_id,
                    status="failed",
                    mode=mode,
                    started_at=started_at,
                    message="cleanup_unavailable",
                    duration_ms=elapsed_ms(cleanup_started),
                )

            current_signature = self._source_file_signature(source_path)
            if current_signature != initial_signature:
                produced_path.unlink(missing_ok=True)
                return self._write_source_scan_cleanup(
                    source_id,
                    status="stale",
                    mode=mode,
                    started_at=started_at,
                    message="source_changed",
                    source_signature=current_signature or {},
                    duration_ms=elapsed_ms(cleanup_started),
                )

            raw_path = self._source_raw_pdf_path(source_id)
            if not raw_path.exists():
                raw_temp_path = raw_path.with_name(f"{raw_path.name}.{uuid.uuid4().hex}.tmp")
                try:
                    shutil.copy2(source_path, raw_temp_path)
                    os.replace(raw_temp_path, raw_path)
                except OSError:
                    raw_temp_path.unlink(missing_ok=True)
                    raise

            os.replace(produced_path, source_path)
            produced_path = None
            self._regenerate_source_preview(source_id, source_path)
            self._delete_source_analyses(source_id)
            final_signature = self._source_file_signature(source_path) or {}
            revision = str(final_signature.get("mtime_ns") or uuid.uuid4())
            result = self._write_source_scan_cleanup(
                source_id,
                status="ready",
                mode=mode,
                started_at=started_at,
                completed_at=self._utc_timestamp(),
                duration_ms=elapsed_ms(cleanup_started),
                revision=revision,
                source_signature=final_signature,
            )
            logger.info(
                "import source scan cleanup applied source_file_id=%s mode=%s dpi=%s duration_ms=%s",
                source_id,
                mode,
                dpi_target,
                result.get("duration_ms"),
            )
            log_import_timing(
                "source_scan_cleanup_ready",
                source_file_id=source_id,
                mode=mode,
                dpi=dpi_target,
                duration_ms=result.get("duration_ms"),
            )
            return result
        except Exception as exc:  # noqa: BLE001 - Staging bleibt mit Rohscan nutzbar
            logger.warning("import source scan cleanup failed source_file_id=%s err=%s", source_id, exc)
            return self._write_source_scan_cleanup(
                source_id,
                status="failed",
                mode=mode,
                started_at=started_at,
                message=str(exc)[:300],
                duration_ms=elapsed_ms(cleanup_started),
            )
        finally:
            if produced_path is not None:
                produced_path.unlink(missing_ok=True)
            candidate_path.unlink(missing_ok=True)

    def _safe_document_filename(self, title: str) -> str:
        normalized = " ".join(str(title or "").split()).strip()
        if not normalized:
            normalized = "Dokument"
        normalized = normalized.replace("/", "-").replace("\\", "-").replace(":", "-")
        if not normalized.lower().endswith(".pdf"):
            normalized = f"{normalized}.pdf"
        return normalized[:200]

    def upload_sources(self, files: list[UploadFile]) -> ImportSourceUploadResponse:
        if not files:
            raise BadRequestError("At least one PDF file is required")

        items: list[ImportSourceRead] = []
        for file in files:
            source_started = now_perf()
            original_name = self._validate_source_file(file)
            source_file_id = str(uuid.uuid4())
            source_path = self._source_pdf_path(source_file_id)
            bytes_written = 0

            try:
                bytes_written = self._store_source_pdf(file, source_path)
                reader = PdfReader(str(source_path))
                page_count = len(reader.pages)
                if page_count <= 0:
                    raise BadRequestError("Uploaded PDF has no pages", details={"filename": original_name})
            except Exception:
                source_path.unlink(missing_ok=True)
                raise
            log_import_timing(
                "source_staged",
                source_file_id=source_file_id,
                original_name=original_name,
                page_count=page_count,
                bytes=bytes_written,
                duration_ms=elapsed_ms(source_started),
            )

            color_profile = self.get_source_color_profile(source_file_id)
            items.append(
                ImportSourceRead(
                    source_file_id=source_file_id,
                    original_name=original_name,
                    page_count=page_count,
                    preview_url=self.source_preview_url(source_file_id),
                    scan_cleanup=self.get_source_scan_cleanup_response(source_file_id),
                    color_page_indices=color_profile["color_page_indices"],
                    color_detection_available=bool(color_profile["color_detection_available"]),
                )
            )

        return ImportSourceUploadResponse(items=items)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return _WHITESPACE_RE.sub(" ", str(value or "")).strip()

    @staticmethod
    def _coerce_llm_scalar(value: object) -> str | None:
        return coerce_llm_scalar(value)

    @staticmethod
    def _normalize_source_file_ids(source_file_ids: list[str]) -> list[str]:
        normalized_ids = []
        seen = set()
        for source_file_id in source_file_ids:
            value = str(source_file_id or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized_ids.append(value)
        return normalized_ids

    @staticmethod
    def _is_valid_source_file_id(source_file_id: str) -> bool:
        try:
            uuid.UUID(str(source_file_id or "").strip())
            return True
        except (TypeError, ValueError):
            return False

    def _extract_text_for_title_suggestion(
        self,
        source_file_ids: list[str],
        *,
        page_scope: str,
        max_pages: int = 5,
        max_chars: int = 12000,
    ) -> tuple[str, int, list[str]]:
        normalized_ids = self._normalize_source_file_ids(source_file_ids)
        if not normalized_ids:
            raise BadRequestError("sourceFileIds is required")

        pages_scanned = 0
        page_refs: list[str] = []
        text_parts: list[str] = []
        for source_file_id in normalized_ids:
            source_path = self.get_source_pdf_path(source_file_id)
            reader = PdfReader(str(source_path))
            if len(reader.pages) <= 0:
                continue

            page_indexes = [0] if page_scope == "first_page" else list(range(min(len(reader.pages), max_pages)))
            for page_index in page_indexes:
                if pages_scanned >= max_pages:
                    break
                page = reader.pages[page_index]
                raw = str(page.extract_text() or "").strip()
                text = self._normalize_text(raw)
                if text:
                    text_parts.append(text)
                page_refs.append(f"{source_file_id}:{page_index}")
                pages_scanned += 1
                if page_scope == "first_page":
                    break
            if page_scope == "first_page" and pages_scanned > 0:
                break
            if pages_scanned >= max_pages:
                break

        merged = "\n\n".join(text_parts).strip()
        if len(merged) > max_chars:
            merged = merged[:max_chars].rstrip()
        return merged, pages_scanned, page_refs

    def _extract_text_with_ocr_fallback(self, source_file_ids: list[str], *, page_scope: str) -> tuple[str, dict[str, object]]:
        """OCR fallback using the lightweight run_ocr_lite path.

        Skips ocrmypdf and heavy NlMeans denoising, but tries several Tesseract
        page segmentation modes. This keeps the synchronous import preview fast
        while making scans with letterheads, footers, or sparse text more robust.
        """
        normalized_ids = [str(sid or "").strip() for sid in source_file_ids if str(sid or "").strip()]
        if not normalized_ids:
            return "", {"status": "empty_sources", "errors": []}

        if shutil.which("tesseract") is None:
            message = "tesseract is not available in the backend runtime"
            logger.warning("stage title ocr unavailable: %s", message)
            return "", {"status": "ocr_unavailable", "errors": [message], "attempts": []}

        ocr_settings = self.settings_service.get_settings().model_dump(mode="json").get("ocr", {})
        language = str(ocr_settings.get("language") or "deu+eng")
        max_sources = 1 if page_scope == "first_page" else 2
        max_pages_per_source = 1 if page_scope == "first_page" else 3
        captured_texts: list[str] = []
        attempts: list[dict[str, object]] = []
        errors: list[str] = []

        for source_file_id in normalized_ids[:max_sources]:
            source_path = self.get_source_pdf_path(source_file_id)
            try:
                reader = PdfReader(str(source_path))
                total_pages = len(reader.pages)
            except Exception as exc:
                logger.warning("stage title ocr: could not read page count source_file_id=%s err=%s", source_file_id, exc)
                total_pages = 1

            page_indexes = list(range(min(total_pages, max_pages_per_source)))
            source_texts: list[str] = []
            for page_idx in page_indexes:
                best_text = ""
                for attempt in _STAGING_OCR_ATTEMPTS:
                    psm = int(attempt["psm"])
                    max_long_side_px = int(attempt["max_long_side_px"])
                    try:
                        text = run_ocr_lite(
                            source_path,
                            page_index=page_idx,
                            language=language,
                            max_long_side_px=max_long_side_px,
                            page_segmentation_mode=psm,
                        )
                        normalized = self._normalize_text(text)
                        attempts.append({
                            "source_file_id": source_file_id,
                            "page_index": page_idx,
                            "psm": psm,
                            "max_long_side_px": max_long_side_px,
                            "chars": len(normalized),
                        })
                        if len(normalized) > len(best_text):
                            best_text = normalized
                        if len(normalized) >= _STAGING_GOOD_TEXT_CHARS:
                            break
                    except Exception as exc:
                        message = f"source={source_file_id} page={page_idx} psm={psm}: {exc}"
                        errors.append(message[:500])
                        logger.warning("stage title ocr lite failed %s", message)
                if best_text:
                    source_texts.append(best_text)

            if source_texts:
                captured_texts.extend(source_texts)
                if page_scope == "first_page":
                    break

        merged = self._normalize_text("\n\n".join(captured_texts))
        status = "ready" if len(merged) >= _STAGING_MIN_TEXT_CHARS else "low_text"
        if not merged and errors:
            status = "ocr_failed"
        return merged, {
            "status": status,
            "language": language,
            "attempts": attempts,
            "errors": errors[:5],
            "chars": len(merged),
        }

    @staticmethod
    def _detect_document_type(text_value: str) -> str:
        return detect_document_type(text_value)

    @staticmethod
    def _normalize_doc_type(value: str | None, allowed_doc_types: list[str] | None = None) -> str | None:
        return normalize_document_type(value, allowed_doc_types)

    @staticmethod
    def _clean_filename_component(value: str, *, max_len: int = 80) -> str:
        normalized = ImportStagingService._normalize_text(value)
        normalized = _INVALID_TITLE_CHARS.sub(" ", normalized)
        normalized = _WHITESPACE_RE.sub(" ", normalized).strip(" .,-_")
        if len(normalized) > max_len:
            normalized = normalized[:max_len].rstrip(" .,-_")
        return normalized

    @staticmethod
    def _normalize_issuer(value: str) -> str:
        return normalize_issuer(value)

    @staticmethod
    def _extract_issuer_from_line(line: str) -> str:
        return extract_issuer_from_line(line)

    @staticmethod
    def _normalize_subject(value: str) -> str:
        return normalize_subject(value)

    @staticmethod
    def _detect_sender(text_value: str) -> str | None:
        return detect_sender(text_value)

    @staticmethod
    def _detect_amount_currency(text_value: str) -> tuple[float | None, str | None]:
        return detect_amount_currency(text_value)

    @staticmethod
    def _detect_subject_heuristic(text_value: str) -> str:
        return detect_subject_heuristic(text_value)

    @staticmethod
    def _is_subject_supported_by_context(subject: str, text_value: str, issuer_value: str = "") -> bool:
        return is_subject_supported_by_context(subject, text_value, issuer_value)

    @classmethod
    def _sanitize_title(cls, value: str, *, fallback: str | None = None, max_len: int = _FILENAME_MAX_LEN) -> str:
        return sanitize_title(value, fallback=fallback, max_len=max_len)

    @classmethod
    def _build_fallback_title(
        cls,
        *,
        doc_type: str,
        sender: str | None,
        date_value: str | None,
        amount: float | None,
        currency: str | None,
    ) -> str:
        return build_fallback_title(
            doc_type=doc_type,
            sender=sender,
            date_value=date_value,
            amount=amount,
            currency=currency,
        )

    @classmethod
    def _extract_json_object(cls, value: str) -> dict[str, object] | None:
        return extract_json_object(value)

    @classmethod
    def _extract_loose_fields(cls, raw_text: str) -> dict[str, object] | None:
        return extract_loose_fields(raw_text)

    @staticmethod
    def _safe_float(value: object) -> float | None:
        return safe_float(value)

    @staticmethod
    def _extract_document_date(text: str) -> str | None:
        return extract_document_date(text)

    @staticmethod
    def _detect_document_type_improved(text: str) -> str:
        return detect_document_type_improved(text)

    @staticmethod
    def _extract_subject_rich(text: str, doc_type: str) -> str | None:
        return extract_subject_rich(text, doc_type)

    @classmethod
    def _generate_tags_from_text(cls, text: str, doc_type: str) -> list[str]:
        return generate_tags_from_text(text, doc_type)

    @staticmethod
    def _select_staging_llm_text(ocr_text: str, max_chars: int) -> str:
        return select_staging_llm_text(ocr_text, max_chars)

    @staticmethod
    def _call_ollama_for_staging(
        ocr_text: str,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_input_chars: int,
        existing_tags: list[str] | None = None,
        allowed_doc_types: list[str] | None = None,
        doc_type_hints: dict[str, str] | None = None,
        naming_examples: list[str] | None = None,
    ) -> dict[str, object] | None:
        """Call Ollama to extract metadata from OCR text.

        Returns a dict with doc_type, issuer, subject, date, tags, amount, currency
        or None if Ollama is unreachable or returns an unparseable response.
        Text is truncated to max_input_chars before sending.

        existing_tags steuert die Tag-Vergabe: das Modell soll – wenn inhaltlich
        passend – vorhandene Tags wiederverwenden statt neue Varianten zu erfinden.
        """
        text_for_llm = ImportStagingService._select_staging_llm_text(ocr_text, max_input_chars)
        if not text_for_llm:
            return None

        tag_names = [str(n).strip() for n in (existing_tags or []) if str(n).strip()]
        if tag_names:
            tag_hint = (
                '\nWICHTIG für "tags": Vergib höchstens 1–2 hochwertige, treffende Schlagworte. '
                "Prüfe ZUERST sorgfältig diese bereits vorhandenen Tags und verwende ein "
                "inhaltlich passendes davon EXAKT in dieser Schreibweise: "
                + ", ".join(tag_names[:80])
                + ". Erstelle nur dann ein NEUES Tag, wenn inhaltlich wirklich KEINES der "
                "vorhandenen passt. Im Zweifel lieber ein vorhandenes Tag oder gar kein Tag "
                "als ein neues – Ziel: so wenige neue Tags wie möglich.\n"
            )
        else:
            tag_hint = (
                '\nWICHTIG für "tags": Vergib höchstens 1–2 hochwertige, treffende deutsche '
                "Schlagworte. Lieber ein einziges präzises Tag als mehrere ungenaue.\n"
            )

        doc_type_names = [str(name).strip() for name in (allowed_doc_types or []) if str(name).strip()]
        if not doc_type_names:
            doc_type_names = sorted(_DOC_TYPES_ALLOWED)
        doc_type_hint = ", ".join(doc_type_names[:120])

        hint_lines: list[str] = []
        if doc_type_hints:
            for name in doc_type_names:
                hint = " ".join(str(doc_type_hints.get(name) or "").split()).strip()
                if hint:
                    hint_lines.append(f"- {name}: {hint}")
                if len(hint_lines) >= 40:
                    break
        hint_block = (
            "Typ-Hinweise zur Wahl von doc_type:\n" + "\n".join(hint_lines) + "\n\n"
            if hint_lines
            else ""
        )

        examples_block = ImportStagingService._build_naming_examples_block(naming_examples)

        prompt = (
            "Extrahiere aus dem folgenden OCR-Text eines deutschen Dokuments die Metadaten. "
            "Antworte NUR mit einem gültigen JSON-Objekt, ohne Markdown, ohne Erklärungen.\n\n"
            f"{hint_block}"
            f"{examples_block}"
            "Felder:\n"
            f'- "doc_type": eines von [{doc_type_hint}]\n'
            '- "issuer": Absender/Aussteller, max. 40 Zeichen, oder null\n'
            '- "subject": Dokumentthema als kurzer Ausdruck, max. 50 Zeichen, oder null\n'
            '- "date": Dokumentdatum als YYYY-MM-DD oder null\n'
            '- "tags": Array mit maximal 1–2 deutschen Schlagworten (vorhandene bevorzugen) oder []\n'
            '- "amount": Gesamtbetrag als Zahl (z.B. 123.45) oder null\n'
            '- "currency": "EUR" oder null\n'
            '- "summary": die 2–4 wichtigsten Fakten des Dokuments als kurzer, sachlicher '
            'Fließtext (z.B. Fristen, Beträge, Aktenzeichen, Kernaussage), max. 240 Zeichen, oder null\n'
            + tag_hint
            + f"\nOCR-Text:\n{text_for_llm}"
        )
        payload = {"model": model, "stream": False, "format": "json", "prompt": prompt}

        raw = request_generation(
            base_url=base_url,
            payload=payload,
            timeout_seconds=timeout_seconds,
            model=model,
            input_chars=len(text_for_llm),
            http_post=httpx.post,
        )
        if raw is None:
            return None

        # Parse JSON (handle possible markdown fences)
        candidate = raw
        if not candidate.startswith("{"):
            m = re.search(r"\{[\s\S]*\}", candidate)
            candidate = m.group(0) if m else ""
        try:
            parsed = json.loads(candidate)
        except Exception:
            logger.warning("ollama staging: could not parse JSON from response: %r", raw[:200])
            return None

        if not isinstance(parsed, dict):
            return None

        # Normalise field values
        def _str(key: str, max_len: int = 80) -> str | None:
            v = ImportStagingService._coerce_llm_scalar(parsed.get(key))
            return v[:max_len] if v else None

        def _first_str(keys: tuple[str, ...], max_len: int = 80) -> str | None:
            for key in keys:
                value = _str(key, max_len)
                if value:
                    return value
            return None

        def _date(key: str) -> str | None:
            v = ImportStagingService._coerce_llm_scalar(parsed.get(key)) or ""
            return v if re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None

        def _tags(key: str) -> list[str]:
            raw_tags = parsed.get(key)
            if not isinstance(raw_tags, list):
                return []
            tags: list[str] = []
            for tag in raw_tags:
                value = ImportStagingService._coerce_llm_scalar(tag)
                if value:
                    tags.append(value)
            return tags[:2]

        def _amount(key: str) -> float | None:
            try:
                raw_value = ImportStagingService._coerce_llm_scalar(parsed.get(key)) or ""
                v = float(raw_value.replace(",", "."))
                return round(v, 2) if v > 0 else None
            except (TypeError, ValueError):
                return None

        return {
            "doc_type": _str("doc_type", 64),
            "issuer": _str("issuer", 40),
            "subject": _str("subject", 50),
            "date": _date("date"),
            "tags": _tags("tags"),
            "amount": _amount("amount"),
            "currency": "EUR" if str(parsed.get("currency") or "").upper() == "EUR" else None,
            "summary": _first_str(("summary", "note", "notes", "ai_summary"), 240),
        }

    @classmethod
    def _extract_rich_metadata(cls, ocr_text: str) -> dict[str, object]:
        """Extract all document metadata from OCR text using rule-based patterns.

        Replaces the broken AI-service call. Extracts: doc_type, issuer, subject,
        amount, currency, date, tags — entirely locally without network calls.

        Passes the ORIGINAL text (with newlines) to functions that rely on line
        structure (sender/issuer, subject). The normalized (collapsed) version is
        used only for keyword matching that doesn't depend on layout.
        """
        if not ocr_text or not ocr_text.strip():
            return {}

        # Keep original for layout-sensitive detection
        # Use normalized (whitespace-collapsed) text for keyword patterns
        normalized = cls._normalize_text(ocr_text)

        doc_type = cls._detect_document_type_improved(ocr_text)
        issuer = cls._detect_sender(ocr_text)          # original text → correct line splitting
        amount, currency = cls._detect_amount_currency(normalized)
        date_iso = cls._extract_document_date(ocr_text)
        subject = (
            cls._extract_subject_rich(ocr_text, doc_type)
            or cls._detect_subject_heuristic(normalized)
        )
        tags = cls._generate_tags_from_text(ocr_text, doc_type)

        return {
            "doc_type": doc_type,
            "issuer": issuer,
            "subject": subject,
            "amount": amount,
            "currency": currency,
            "date": date_iso,
            "tags": tags,
        }

    def _extract_metadata_with_ai(self, ocr_text: str, *, today_display: str) -> tuple[dict[str, object] | None, str]:
        text = self._normalize_text(ocr_text)
        if not text:
            return None, ""

        user_prompt = (
            "Extrahiere aus dem OCR-Text folgende Felder:\n"
            "- doc_type: eins von [Rechnung, Quittung, Mahnung, Vertrag, Kündigung, Brief, Bescheid, Protokoll, Sonstiges]\n"
            "- issuer: Absender/Firma (kurz, max 30 Zeichen, ohne Rechtsform-Suffix wenn möglich)\n"
            "- subject: sehr kurzer Betreff (max 40 Zeichen)\n"
            "- amount: Gesamtbetrag als Zahl mit Punkt (z.B. 123.45) oder null\n"
            "- currency: EUR oder null\n"
            "- date: Dokumentdatum im Format YYYY-MM-DD (z.B. 2024-03-15) oder null\n"
            "- tags: Liste von maximal 1-2 hochwertigen Schlagworten als Strings (z.B. [\"Strom\"]) oder []\n\n"
            "Regeln:\n"
            "- doc_type: erkenne Rechnung robust (z.B. Rechnung, Invoice, RG, Rechnungsnr).\n"
            "- issuer: bevorzuge die erste erkennbare Firma/Marke im Kopfbereich.\n"
            "- subject: KEIN voller Satz, KEIN Datum, KEINE Rechnungsnummer.\n"
            "- amount: wenn mehrere Beträge, nimm Endbetrag (Summe/Total/Gesamtbetrag).\n"
            "- date: Rechnungs-/Brief-/Vertragsdatum – NICHT das heutige Datum.\n"
            "- tags: thematische Begriffe, die das Dokument inhaltlich beschreiben.\n\n"
            f"OCR:\n<<<{text[:12000]}>>>\n\n"
            f"Heutiges Datum: {today_display}\n\n"
            "Antworte nur mit JSON im Format:\n"
            "{\n"
            '  "doc_type": "...",\n'
            '  "issuer": "...",\n'
            '  "subject": "...",\n'
            '  "amount": 123.45,\n'
            '  "currency": "EUR",\n'
            '  "date": "2024-03-15",\n'
            '  "tags": ["Begriff1", "Begriff2"]\n'
            "}"
        )
        payload = {
            "model": "default",
            "system_prompt": (
                "Du extrahierst Metadaten aus OCR-Text. Antworte AUSSCHLIESSLICH mit gültigem JSON. "
                "Keine Erklärungen, kein Markdown, kein Text außerhalb des JSON. "
                "Wenn ein Feld nicht sicher ist, setze es auf null."
            ),
            "max_sentences": 1,
            "max_tokens": 300,
            "temperature": 0.1,
            "question": "Extrahiere Metadaten als JSON.",
            "user_prompt": user_prompt,
            "contexts": [],
        }
        try:
            response = httpx.post(
                f"{settings.ai_base_url.rstrip('/')}/chat",
                json=payload,
                timeout=settings.ai_chat_timeout_seconds,
            )
            response.raise_for_status()
            answer = str(response.json().get("answer") or "").strip()
            logger.info("SuggestTitle: llm_raw=%r", answer)
        except Exception as exc:  # pragma: no cover - runtime/network
            logger.warning("stage title ai suggestion failed: %s", exc)
            return None, ""

        parsed = self._extract_json_object(answer)
        if parsed is None:
            parsed = self._extract_loose_fields(answer)
            if parsed is None:
                return None, answer

        doc_type = self._normalize_doc_type(str(parsed.get("doc_type") or ""))
        issuer = self._normalize_issuer(str(parsed.get("issuer") or "")) or None
        subject = self._normalize_subject(str(parsed.get("subject") or "")) or None
        amount = self._safe_float(parsed.get("amount"))
        currency = self._normalize_text(str(parsed.get("currency") or "")).upper()[:3] or None
        if currency not in {"EUR", None}:
            currency = None

        import re as _re
        date_raw = str(parsed.get("date") or "").strip()
        doc_date = date_raw if _re.match(r"^\d{4}-\d{2}-\d{2}$", date_raw) else None

        tags_raw = parsed.get("tags")
        doc_tags: list[str] = (
            [str(t).strip() for t in tags_raw if t and str(t).strip()][:2]
            if isinstance(tags_raw, list)
            else []
        )

        return {
            "doc_type": doc_type,
            "issuer": issuer,
            "subject": subject,
            "amount": amount,
            "currency": currency,
            "date": doc_date,
            "tags": doc_tags,
        }, answer

    @classmethod
    def _format_euro(cls, amount: float) -> str:
        return format_euro(amount)

    @classmethod
    def _build_note_from_metadata(
        cls,
        *,
        issuer: str | None,
        subject: str | None,
        doc_type: str | None,
        date_iso: str | None,
        amount: float | None,
        currency: str | None,
        max_len: int = 500,
    ) -> str | None:
        return build_note_from_metadata(
            issuer=issuer,
            subject=subject,
            doc_type=doc_type,
            date_iso=date_iso,
            amount=amount,
            currency=currency,
            max_len=max_len,
        )

    @classmethod
    def _clip_with_ellipsis(cls, value: str, max_len: int) -> str:
        normalized = cls._clean_filename_component(value, max_len=max_len + 8)
        if len(normalized) <= max_len:
            return normalized
        if max_len <= 1:
            return normalized[:max_len]
        return f"{normalized[: max_len - 1].rstrip()}…"

    @classmethod
    def _build_filename_from_meta(cls, meta: dict[str, object]) -> str:
        return build_filename_from_meta(meta)

    def _load_existing_tag_names(self, limit: int = 200) -> list[str]:
        """Vorhandene Tag-Namen für die KI-Tag-Vergabe (bevorzugt wiederverwenden)."""
        try:
            rows = self.db.execute(select(Tag.name).order_by(Tag.name).limit(limit)).scalars().all()
        except Exception as exc:  # noqa: BLE001 - best effort, darf die Erkennung nie blockieren
            logger.warning("stage title: could not load existing tags: %s", exc)
            return []
        return [str(name).strip() for name in rows if name and str(name).strip()]

    def _resolve_correspondent(self, sender_raw: str | None, ocr_text: str | None) -> dict[str, object] | None:
        """Rohen Absender/OCR-Text auf einen kanonischen Korrespondenten abbilden.

        Best effort – Fehler dürfen den Titelvorschlag nie blockieren.
        """
        if not (str(sender_raw or "").strip() or str(ocr_text or "").strip()):
            return None
        try:
            match = CorrespondentMatchingService(self.db, self.owner_id).resolve(sender=sender_raw, ocr_text=ocr_text)
        except Exception as exc:  # noqa: BLE001 - Korrespondenten-Matching ist optional
            logger.warning("stage title: correspondent matching failed: %s", exc)
            return None
        if match is None:
            return None
        return {
            "id": str(match.correspondent_id),
            "name": match.name,
            "short_name": match.short_name,
            "matched_by": match.matched_by,
            "matched_value": match.matched_value,
        }

    @staticmethod
    def _looks_like_default_title(value: str) -> bool:
        """Erkennt generische Scan-/Fallback-Titel, die kein Schreibmuster sind."""
        normalized = " ".join(str(value or "").split()).strip().lower()
        if not normalized:
            return True
        # z. B. "Scan", "Scan - 03-2024", "Dokument", "Neues Dokument"
        return bool(re.match(r"^(scan|dokument|neues dokument|unbenannt|untitled)\b", normalized))

    @staticmethod
    def _build_naming_examples_block(
        examples: list[str] | None,
        *,
        max_examples: int = 3,
        max_len: int = 80,
    ) -> str:
        """Kurzer Few-Shot-Block aus bestehenden Dateinamen (reine Funktion, testbar).

        Liefert "" wenn keine brauchbaren Beispiele vorhanden sind. Die Beispiele
        sind als Stilvorlage für den ``subject``-Slot gedacht – nicht zum wörtlichen
        Übernehmen.
        """
        return build_naming_examples_block(examples, max_examples=max_examples, max_len=max_len)

    def _load_naming_examples(
        self,
        *,
        document_type: str | None,
        correspondent_id: str | uuid.UUID | None,
        limit: int = 3,
    ) -> list[str]:
        """Top-N kuratierte Dateinamen ähnlicher Dokumente als Few-Shot-Vorlage.

        Zuerst nach (document_type UND correspondent_id) filtern; liefert das zu
        wenige Treffer, wird auf document_type-only zurückgefallen. Best effort –
        darf den Titelvorschlag nie blockieren.
        """
        doc_type = " ".join(str(document_type or "").split()).strip()
        if not doc_type or doc_type.casefold() == "sonstiges":
            return []

        normalized_correspondent: uuid.UUID | None = None
        if correspondent_id is not None:
            try:
                normalized_correspondent = uuid.UUID(str(correspondent_id))
            except (ValueError, TypeError):
                normalized_correspondent = None

        def _query(with_correspondent: bool) -> list[str]:
            stmt = (
                select(Document.display_name)
                .where(
                    Document.is_deleted.is_(False),
                    Document.display_name.is_not(None),
                    func.lower(Document.document_type) == doc_type.lower(),
                )
                .order_by(Document.document_date.desc().nullslast(), Document.created_at.desc())
                .limit(limit * 4)
            )
            if with_correspondent and normalized_correspondent is not None:
                stmt = stmt.where(Document.correspondent_id == normalized_correspondent)
            if self.owner_id is not None:
                stmt = stmt.where(Document.owner_id == self.owner_id)
            try:
                rows = self.db.execute(stmt).scalars().all()
            except Exception as exc:  # noqa: BLE001 - Few-Shot ist optional
                logger.warning("stage title: naming example query failed: %s", exc)
                return []
            result: list[str] = []
            seen: set[str] = set()
            for name in rows:
                cleaned = " ".join(str(name or "").split()).strip()
                if not cleaned or self._looks_like_default_title(cleaned):
                    continue
                key = cleaned.casefold()
                if key in seen:
                    continue
                seen.add(key)
                result.append(cleaned)
                if len(result) >= limit:
                    break
            return result

        examples = _query(with_correspondent=True)
        if not examples:
            examples = _query(with_correspondent=False)
        return examples

    def _build_stage_title_result(
        self,
        *,
        extracted_text: str,
        normalized_scope: str,
        page_refs: list[str],
        ocr_pending: bool,
        ocr_diagnostics: dict[str, object],
        stage_id: str | None = None,
        use_ollama: bool = True,
    ) -> dict[str, object]:
        preview = extracted_text[:300].replace("\n", " ").replace("\r", " ")
        logger.info(
            "SuggestTitle: stage=%s scope=%s pages=%s ocr_len=%d ocr_preview=%r pending_ocr=%s",
            str(stage_id or "").strip() or "-",
            normalized_scope,
            page_refs,
            len(extracted_text),
            preview,
            ocr_pending,
        )
        today_filename = datetime.now(timezone.utc).strftime("%d-%m-%Y")
        if ocr_pending:
            diagnostic_status = str(ocr_diagnostics.get("status") or "ocr_failed")
            if diagnostic_status in {"ocr_unavailable", "ocr_failed"}:
                return {
                    "status": "error",
                    "suggestion": f"Scan{_FILENAME_SEPARATOR}{today_filename}",
                    "used_fallback": True,
                    "meta": {
                        "doc_type": None,
                        "issuer": None,
                        "subject": None,
                        "amount": None,
                        "currency": None,
                        "date": None,
                        "document_type": None,
                        "category": None,
                        "tags": [],
                        "analysis_status": diagnostic_status,
                        "analysis_error": "; ".join(str(e) for e in ocr_diagnostics.get("errors", []) if e)[:500] or None,
                        "analysis_phase": "rule",
                        "ocr": ocr_diagnostics,
                    },
                }
            return {
                "status": "ready",
                "suggestion": f"Scan{_FILENAME_SEPARATOR}{today_filename}",
                "used_fallback": True,
                "meta": {
                    "doc_type": None,
                    "issuer": None,
                    "subject": None,
                    "amount": None,
                    "currency": None,
                    "date": None,
                    "document_type": None,
                    "category": None,
                    "tags": [],
                    "analysis_status": "no_text",
                    "analysis_phase": "rule",
                    "ocr": ocr_diagnostics,
                },
            }

        if len(extracted_text.strip()) < _STAGING_MIN_TEXT_CHARS:
            return {
                "status": "ready",
                "suggestion": f"Scan{_FILENAME_SEPARATOR}{today_filename}",
                "used_fallback": True,
                "meta": {
                    "doc_type": None,
                    "issuer": None,
                    "subject": None,
                    "amount": None,
                    "currency": None,
                    "date": None,
                    "document_type": None,
                    "category": None,
                    "tags": [],
                    "analysis_status": "low_text",
                    "analysis_phase": "rule",
                    "ocr": ocr_diagnostics,
                },
            }

        runtime_settings = self.settings_service.get_settings().model_dump(mode="json")
        ollama_cfg = runtime_settings.get("ollama") or {}
        existing_tag_names = self._load_existing_tag_names()
        doc_type_vocab = load_active_document_type_vocab(self.db, self.owner_id)
        active_doc_type_names = document_type_names(doc_type_vocab)
        ollama_rich: dict[str, object] | None = None
        if use_ollama and ollama_cfg.get("enabled"):
            rough_doc_type = self._detect_document_type_improved(extracted_text)
            rough_correspondent = self._resolve_correspondent(None, extracted_text)
            naming_examples = self._load_naming_examples(
                document_type=rough_doc_type,
                correspondent_id=(rough_correspondent or {}).get("id"),
            )
            ollama_rich = self._call_ollama_for_staging(
                extracted_text,
                base_url=str(ollama_cfg.get("base_url") or "http://localhost:11434"),
                model=str(ollama_cfg.get("model") or "llama3.2:3b"),
                timeout_seconds=float(ollama_cfg.get("timeout_seconds") or 90.0),
                max_input_chars=int(ollama_cfg.get("max_input_chars") or 800),
                existing_tags=existing_tag_names,
                allowed_doc_types=active_doc_type_names,
                doc_type_hints=document_type_hint_map(doc_type_vocab),
                naming_examples=naming_examples,
            )
            if ollama_rich:
                logger.info("SuggestTitle: ollama extraction succeeded stage=%s", str(stage_id or "").strip() or "-")

        rule_rich = self._extract_rich_metadata(extracted_text)
        if ollama_rich:
            rich: dict[str, object] = {
                "doc_type": ollama_rich.get("doc_type") or rule_rich.get("doc_type"),
                "issuer": ollama_rich.get("issuer") or rule_rich.get("issuer"),
                "subject": ollama_rich.get("subject") or rule_rich.get("subject"),
                "date": ollama_rich.get("date") or rule_rich.get("date"),
                "tags": ollama_rich.get("tags") or rule_rich.get("tags") or [],
                "amount": ollama_rich.get("amount") if ollama_rich.get("amount") is not None else rule_rich.get("amount"),
                "currency": ollama_rich.get("currency") or rule_rich.get("currency"),
                "summary": ollama_rich.get("summary") or rule_rich.get("summary"),
            }
        else:
            rich = rule_rich

        normalized_doc_type = self._normalize_doc_type(
            self._coerce_llm_scalar(rich.get("doc_type")) or "",
            active_doc_type_names,
        ) or "Sonstiges"
        issuer_raw = self._coerce_llm_scalar(rich.get("issuer"))
        subject_raw = self._coerce_llm_scalar(rich.get("subject"))
        issuer = self._normalize_issuer(issuer_raw or "") or "Unbekannt"
        subject = self._normalize_subject(subject_raw or "") or None
        normalized_amount = self._safe_float(rich.get("amount"))
        if normalized_amount is not None and normalized_amount <= 0:
            normalized_amount = None
        currency = "EUR" if (normalized_amount is not None) else None
        raw_date = self._coerce_llm_scalar(rich.get("date")) or ""
        final_date = raw_date if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date) else None
        if final_date:
            try:
                parsed_date = datetime.strptime(final_date, "%Y-%m-%d").date()
            except ValueError:
                parsed_date = None
            if parsed_date is None:
                final_date = None
            else:
                today = datetime.now().date()
                if parsed_date > today or parsed_date.year < 1990:
                    final_date = None
        tags_val = rich.get("tags")
        final_tags: list[str] = []
        if isinstance(tags_val, list):
            for tag in tags_val:
                value = self._coerce_llm_scalar(tag)
                if value:
                    final_tags.append(value)
            final_tags = final_tags[:2]
        if final_tags and existing_tag_names:
            existing_by_lower = {name.casefold(): name for name in existing_tag_names}
            deduped: list[str] = []
            seen_lower: set[str] = set()
            for tag in final_tags:
                canonical = existing_by_lower.get(tag.casefold(), tag)
                key = canonical.casefold()
                if key not in seen_lower:
                    seen_lower.add(key)
                    deduped.append(canonical)
            final_tags = deduped

        final_note = self._coerce_llm_scalar(rich.get("summary")) or self._build_note_from_metadata(
            issuer=issuer,
            subject=subject,
            doc_type=normalized_doc_type,
            date_iso=final_date,
            amount=normalized_amount,
            currency=currency,
        )

        sender_raw = issuer_raw
        correspondent_info = self._resolve_correspondent(sender_raw, extracted_text)
        document_type = normalized_doc_type

        merged_meta: dict[str, object] = {
            "doc_type": normalized_doc_type,
            "document_type": document_type,
            "issuer": issuer,
            "subject": subject or "Ohne Betreff",
            "amount": normalized_amount,
            "currency": currency,
            "date": final_date,
            "correspondent": correspondent_info,
        }
        suggestion = NamingTemplateService(self.db).build_filename(merged_meta)

        retention_meta: dict[str, object] | None = None
        if use_ollama:
            document_date_obj: date | None = None
            if final_date:
                try:
                    document_date_obj = datetime.strptime(final_date, "%Y-%m-%d").date()
                except ValueError:
                    document_date_obj = None
            try:
                retention_meta = evaluate_retention_suggestion(
                    runtime_settings,
                    ocr_text=extracted_text,
                    document_type=normalized_doc_type,
                    tags=tuple(final_tags),
                    document_date=document_date_obj,
                    document_id=str(stage_id or "staging"),
                )
            except Exception as exc:  # noqa: BLE001 - Aufbewahrungsvorschlag darf den Titel nicht blockieren
                logger.warning("staging retention suggestion failed stage=%s err=%s", str(stage_id or "-"), exc)
                retention_meta = None

        analysis_phase = "llm" if ollama_rich else "rule"
        return {
            "status": "ready",
            "suggestion": suggestion,
            "used_fallback": not bool(subject),
            "meta": {
                "doc_type": normalized_doc_type,
                "issuer": issuer,
                "subject": subject,
                "amount": normalized_amount,
                "currency": currency,
                "date": final_date,
                "document_type": document_type,
                "category": document_type,
                "sender_raw": sender_raw,
                "correspondent": correspondent_info,
                "tags": final_tags,
                "note": final_note,
                "retention": retention_meta,
                "analysis_status": "ready",
                "analysis_phase": analysis_phase,
                "ocr": ocr_diagnostics,
            },
        }

    def suggest_stage_title(
        self,
        source_file_ids: list[str],
        *,
        page_scope: str = "first_page",
        stage_id: str | None = None,
    ) -> dict[str, object]:
        request_started = now_perf()
        normalized_scope = str(page_scope or "first_page").strip().lower()
        if normalized_scope not in {"first_page", "all_pages"}:
            raise BadRequestError("pageScope must be first_page or all_pages")
        normalized_ids = self._normalize_source_file_ids(source_file_ids)
        if not normalized_ids:
            raise BadRequestError("sourceFileIds is required")
        is_cacheable_single_source = (
            normalized_scope == "first_page" and
            len(normalized_ids) == 1 and
            self._is_valid_source_file_id(normalized_ids[0])
        )
        if is_cacheable_single_source:
            cached = self.get_source_analysis(normalized_ids[0])
            # Der Worker legt zuerst eine schnelle regelbasierte Analyse ab und
            # verfeinert sie danach mit Ollama. Sie ist bereits ein brauchbares
            # Ergebnis; auf dem Pi darf der API-Request sie nicht ignorieren und
            # parallel dieselbe OCR/LLM-Arbeit noch einmal starten.
            if cached:
                log_import_timing(
                    "analysis_cache_hit",
                    source_file_id=normalized_ids[0],
                    stage_id=stage_id,
                    phase=str((cached.get("meta") if isinstance(cached, dict) else {}).get("analysis_phase") or ""),
                    total_ms=elapsed_ms(request_started),
                )
                return cached
            if self.is_source_preanalysis_pending(normalized_ids[0]):
                return {
                    "status": "pending_ocr",
                    "suggestion": "",
                    "used_fallback": True,
                    "meta": {
                        "analysis_status": "pending_ocr",
                        "analysis_phase": "worker_queue",
                        "ocr": {"status": "pending_ocr"},
                    },
                }

        embedded_started = now_perf()
        extracted_text, _pages_scanned, page_refs = self._extract_text_for_title_suggestion(
            normalized_ids,
            page_scope=normalized_scope,
            max_pages=5 if normalized_scope == "all_pages" else 1,
            max_chars=12000,
        )
        log_import_timing(
            "analysis_embedded_text",
            source_file_id=normalized_ids[0] if len(normalized_ids) == 1 else None,
            stage_id=stage_id,
            page_scope=normalized_scope,
            chars=len(extracted_text),
            page_refs=page_refs,
            duration_ms=elapsed_ms(embedded_started),
        )
        ocr_pending = False
        ocr_diagnostics: dict[str, object] = {"status": "embedded_text", "chars": len(extracted_text)}
        if not extracted_text:
            ocr_started = now_perf()
            extracted_text, ocr_diagnostics = self._extract_text_with_ocr_fallback(normalized_ids, page_scope=normalized_scope)
            if len(extracted_text) > 12000:
                extracted_text = extracted_text[:12000].rstrip()
            if not extracted_text:
                ocr_pending = True
            log_import_timing(
                "analysis_ocr_fallback",
                source_file_id=normalized_ids[0] if len(normalized_ids) == 1 else None,
                stage_id=stage_id,
                page_scope=normalized_scope,
                status=str(ocr_diagnostics.get("status") or ""),
                chars=len(extracted_text),
                attempts=len(ocr_diagnostics.get("attempts") or []),
                duration_ms=elapsed_ms(ocr_started),
            )

        build_started = now_perf()
        result = self._build_stage_title_result(
            extracted_text=extracted_text,
            normalized_scope=normalized_scope,
            page_refs=page_refs,
            ocr_pending=ocr_pending,
            ocr_diagnostics=ocr_diagnostics,
            stage_id=stage_id,
            use_ollama=True,
        )
        build_ms = elapsed_ms(build_started)
        if is_cacheable_single_source:
            phase = str((result.get("meta") if isinstance(result, dict) else {}).get("analysis_phase") or "llm")
            try:
                result = self.store_source_analysis(
                    normalized_ids[0],
                    result,
                    page_scope=normalized_scope,
                    analysis_phase=phase,
                )
            except Exception as exc:  # noqa: BLE001 - Cache darf den Vorschlag nicht blockieren
                logger.warning("stage title analysis cache write failed source_file_id=%s err=%s", normalized_ids[0], exc)
        result_meta = result.get("meta") if isinstance(result, dict) else {}
        log_import_timing(
            "analysis_request_done",
            source_file_id=normalized_ids[0] if len(normalized_ids) == 1 else None,
            stage_id=stage_id,
            page_scope=normalized_scope,
            status=str(result.get("status") or "") if isinstance(result, dict) else "",
            phase=str(result_meta.get("analysis_phase") or "") if isinstance(result_meta, dict) else "",
            build_ms=build_ms,
            total_ms=elapsed_ms(request_started),
        )
        return result

    def preanalyze_source(self, source_file_id: str, *, page_scope: str = "first_page") -> dict[str, object] | None:
        """Build and cache import analysis before the dialog asks for it.

        The rule result is written first so the UI can fill fields quickly. When
        Ollama is enabled, the same OCR text is then refined by the model and
        stored over the rule result; the inbox SSE digest changes because the
        sidecar JSON changed.
        """
        normalized_ids = self._normalize_source_file_ids([source_file_id])
        if not normalized_ids:
            return None
        normalized_scope = "all_pages" if str(page_scope or "").strip().lower() == "all_pages" else "first_page"
        source_id = normalized_ids[0]
        preanalysis_started = now_perf()
        cached = self.get_source_analysis(source_id)
        cached_phase = str((cached.get("meta") if isinstance(cached, dict) else {}).get("analysis_phase") or "")
        if cached and cached_phase == "llm":
            log_import_timing(
                "preanalysis_cache_hit",
                source_file_id=source_id,
                phase=cached_phase,
                total_ms=elapsed_ms(preanalysis_started),
            )
            return cached

        embedded_started = now_perf()
        extracted_text, _pages_scanned, page_refs = self._extract_text_for_title_suggestion(
            normalized_ids,
            page_scope=normalized_scope,
            max_pages=5 if normalized_scope == "all_pages" else 1,
            max_chars=12000,
        )
        log_import_timing(
            "preanalysis_embedded_text",
            source_file_id=source_id,
            page_scope=normalized_scope,
            chars=len(extracted_text),
            page_refs=page_refs,
            duration_ms=elapsed_ms(embedded_started),
        )
        ocr_pending = False
        ocr_diagnostics: dict[str, object] = {"status": "embedded_text", "chars": len(extracted_text)}
        if not extracted_text:
            ocr_started = now_perf()
            extracted_text, ocr_diagnostics = self._extract_text_with_ocr_fallback(normalized_ids, page_scope=normalized_scope)
            if len(extracted_text) > 12000:
                extracted_text = extracted_text[:12000].rstrip()
            if not extracted_text:
                ocr_pending = True
            log_import_timing(
                "preanalysis_ocr_fallback",
                source_file_id=source_id,
                page_scope=normalized_scope,
                status=str(ocr_diagnostics.get("status") or ""),
                chars=len(extracted_text),
                attempts=len(ocr_diagnostics.get("attempts") or []),
                duration_ms=elapsed_ms(ocr_started),
            )

        rule_started = now_perf()
        rule_result = self._build_stage_title_result(
            extracted_text=extracted_text,
            normalized_scope=normalized_scope,
            page_refs=page_refs,
            ocr_pending=ocr_pending,
            ocr_diagnostics=ocr_diagnostics,
            stage_id=source_id,
            use_ollama=False,
        )
        try:
            rule_result = self.store_source_analysis(
                source_id,
                rule_result,
                page_scope=normalized_scope,
                analysis_phase="rule",
            )
        except Exception as exc:  # noqa: BLE001 - Voranalyse ist best effort
            logger.warning("import source rule analysis cache write failed source_file_id=%s err=%s", source_id, exc)
        log_import_timing(
            "preanalysis_rule_cached",
            source_file_id=source_id,
            page_scope=normalized_scope,
            status=str(rule_result.get("status") or ""),
            duration_ms=elapsed_ms(rule_started),
            total_ms=elapsed_ms(preanalysis_started),
        )

        if ocr_pending:
            return rule_result

        runtime_settings = self.settings_service.get_settings().model_dump(mode="json")
        ollama_cfg = runtime_settings.get("ollama") or {}
        if not ollama_cfg.get("enabled"):
            return rule_result

        llm_started = now_perf()
        llm_result = self._build_stage_title_result(
            extracted_text=extracted_text,
            normalized_scope=normalized_scope,
            page_refs=page_refs,
            ocr_pending=ocr_pending,
            ocr_diagnostics=ocr_diagnostics,
            stage_id=source_id,
            use_ollama=True,
        )
        phase = str((llm_result.get("meta") if isinstance(llm_result, dict) else {}).get("analysis_phase") or "llm")
        try:
            stored_llm_result = self.store_source_analysis(
                source_id,
                llm_result,
                page_scope=normalized_scope,
                analysis_phase=phase,
            )
            log_import_timing(
                "preanalysis_llm_cached",
                source_file_id=source_id,
                page_scope=normalized_scope,
                status=str(stored_llm_result.get("status") or ""),
                phase=phase,
                duration_ms=elapsed_ms(llm_started),
                total_ms=elapsed_ms(preanalysis_started),
            )
            return stored_llm_result
        except Exception as exc:  # noqa: BLE001 - UI kann immer noch synchron anfragen
            logger.warning("import source llm analysis cache write failed source_file_id=%s err=%s", source_id, exc)
            log_import_timing(
                "preanalysis_llm_failed",
                source_file_id=source_id,
                page_scope=normalized_scope,
                phase=phase,
                duration_ms=elapsed_ms(llm_started),
                total_ms=elapsed_ms(preanalysis_started),
            )
            return llm_result

    def _load_source_reader(self, source_file_id: str, reader_cache: dict[str, PdfReader]) -> PdfReader:
        cached = reader_cache.get(source_file_id)
        if cached is not None:
            return cached

        source_path = self._source_pdf_path(source_file_id)
        if not source_path.exists() or not source_path.is_file():
            raise BadRequestError("Staging source PDF not found", details={"source_file_id": source_file_id})

        try:
            reader = PdfReader(str(source_path))
        except Exception as exc:
            raise BadRequestError("Could not read staging source PDF", details={"source_file_id": source_file_id}) from exc

        if len(reader.pages) <= 0:
            raise BadRequestError("Staging source PDF has no pages", details={"source_file_id": source_file_id})

        reader_cache[source_file_id] = reader
        return reader

    def _is_fast_path_document(self, pages: list, reader: PdfReader, source_file_id: str) -> bool:
        if not pages:
            return False
        if len(pages) != len(reader.pages):
            return False
        for expected_index, page in enumerate(pages):
            if page.source_file_id != source_file_id:
                return False
            if page.page_index != expected_index:
                return False
            if page.rotation != 0:
                return False
            if page.color_mode != "auto":
                return False
        return True

    def _source_path_for_color_mode(self, source_file_id: str, color_mode: str) -> Path:
        """Liefert für explizite Farbwahl wieder den unveränderten Scan.

        Die automatische Scan-Bereinigung ersetzt die Staging-Datei, legt davor
        aber eine .raw.pdf ab. Damit kann ein Nutzer vor dem Import bewusst
        wieder Farbe wählen. War der Originalscan selbst schon schwarz-weiß,
        kann und soll diese Auswahl selbstverständlich keine Farben erfinden.
        """
        if color_mode == "color":
            raw_path = self._source_raw_pdf_path(source_file_id)
            if raw_path.exists() and raw_path.is_file():
                return raw_path
        return self._source_pdf_path(source_file_id)

    def _manual_color_mode_dpi(self) -> int:
        _, dpi_target = self._scan_cleanup_settings()
        return dpi_target

    def _append_page_with_color_mode(self, writer: PdfWriter, page, reader_cache: dict[str, PdfReader]) -> None:
        color_mode = str(page.color_mode or "auto")
        source_path = self._source_path_for_color_mode(page.source_file_id, color_mode)
        cache_key = f"{source_path}:{color_mode}"
        reader = reader_cache.get(cache_key)
        if reader is None:
            try:
                reader = PdfReader(str(source_path))
            except Exception as exc:
                raise BadRequestError("Could not read staging source PDF") from exc
            reader_cache[cache_key] = reader
        if page.page_index >= len(reader.pages):
            raise BadRequestError(
                "page_index is out of range",
                details={"source_file_id": page.source_file_id, "page_index": page.page_index},
            )

        if color_mode in {"auto", "color"}:
            writer.add_page(reader.pages[page.page_index])
        else:
            staging_root = self._staging_root()
            source_page_path = staging_root / f"color-source-{uuid.uuid4()}.pdf"
            converted_path = staging_root / f"color-result-{uuid.uuid4()}.pdf"
            try:
                source_writer = PdfWriter()
                source_writer.add_page(reader.pages[page.page_index])
                with source_page_path.open("wb") as output:
                    source_writer.write(output)
                if color_mode == "bw":
                    result = build_bw_pdf(
                        source_page_path, converted_path, dpi_target=self._manual_color_mode_dpi()
                    )
                else:
                    result = build_grayscale_pdf(source_page_path, converted_path, dpi_target=self._manual_color_mode_dpi())
                if result is None:
                    raise StorageError("Could not apply selected color mode")
                writer.add_page(PdfReader(str(result)).pages[0])
            finally:
                source_page_path.unlink(missing_ok=True)
                converted_path.unlink(missing_ok=True)

    def _build_document_pdf(self, title: str, pages: list, reader_cache: dict[str, PdfReader]) -> tuple[Path, int]:
        if not pages:
            raise BadRequestError("Document has no pages")

        staging_root = self._staging_root()
        staging_root.mkdir(parents=True, exist_ok=True)
        assembled_path = staging_root / f"assembled-{uuid.uuid4()}.pdf"

        source_file_id = pages[0].source_file_id
        single_source = len({page.source_file_id for page in pages}) == 1
        if single_source:
            reader = self._load_source_reader(source_file_id, reader_cache)
            if self._is_fast_path_document(pages, reader, source_file_id):
                shutil.copy2(self._source_pdf_path(source_file_id), assembled_path)
                return assembled_path, len(reader.pages)

        writer = PdfWriter()
        for page in pages:
            self._append_page_with_color_mode(writer, page, reader_cache)
            if page.rotation:
                writer.pages[-1].rotate(page.rotation)

        if len(writer.pages) <= 0:
            raise BadRequestError("Document has no pages")

        with assembled_path.open("wb") as output:
            writer.write(output)

        return assembled_path, len(writer.pages)

    def _scan_cleanup_mode_for_committed_pages(self, pages: list) -> str | None:
        source_ids = {str(page.source_file_id or "").strip() for page in pages}
        source_ids.discard("")
        if not source_ids:
            return None
        modes: set[str] = set()
        for source_file_id in source_ids:
            payload = self._read_source_scan_cleanup(source_file_id)
            if not isinstance(payload, dict) or str(payload.get("status") or "") != "ready":
                return None
            mode = normalize_scan_cleanup_mode(payload.get("mode"))
            if mode not in {"white", "bw"}:
                return None
            modes.add(mode)
        if len(modes) == 1:
            return next(iter(modes))
        return "mixed"

    def _cleanup_source_files(self, source_file_ids: set[str]) -> None:
        for source_file_id in source_file_ids:
            try:
                source_path = self._source_pdf_path(source_file_id)
                preview_path = self._source_preview_path(source_file_id)
            except BadRequestError:
                continue
            source_path.unlink(missing_ok=True)
            preview_path.unlink(missing_ok=True)
            self._delete_source_analyses(source_file_id)
            self._delete_source_scan_cleanup_artifacts(source_file_id)

    def delete_source_file(self, source_file_id: str) -> None:
        source_path = self._source_pdf_path(source_file_id)
        preview_path = self._source_preview_path(source_file_id)
        try:
            source_path.unlink(missing_ok=True)
            preview_path.unlink(missing_ok=True)
            self._delete_source_analyses(source_file_id)
            self._delete_source_scan_cleanup_artifacts(source_file_id)
        except OSError as exc:
            raise StorageError("Could not delete staged source PDF") from exc

    def delete_source_pages(self, source_file_id: str, page_indices: list[int]) -> int:
        source_path = self._source_pdf_path(source_file_id)
        if not source_path.exists():
            raise BadRequestError("Staged source PDF was not found")

        delete_indices = sorted({int(index) for index in page_indices})
        if not delete_indices:
            raise BadRequestError("page_indices is required")

        try:
            reader = PdfReader(str(source_path))
            page_count = len(reader.pages)
        except Exception as exc:
            raise BadRequestError("Could not read staged source PDF") from exc

        invalid_indices = [index for index in delete_indices if index < 0 or index >= page_count]
        if invalid_indices:
            raise BadRequestError(
                "page_index is out of range",
                details={"invalid_page_indices": invalid_indices, "page_count": page_count},
            )

        remaining_indices = [index for index in range(page_count) if index not in set(delete_indices)]
        if not remaining_indices:
            self.delete_source_file(source_file_id)
            return 0

        writer = PdfWriter()
        for page_index in remaining_indices:
            writer.add_page(reader.pages[page_index])

        temp_path = source_path.with_name(f"{source_path.stem}.{uuid.uuid4().hex}.tmp.pdf")
        try:
            with temp_path.open("wb") as output:
                writer.write(output)
            os.replace(temp_path, source_path)
            self._source_preview_path(source_file_id).unlink(missing_ok=True)
            self._delete_source_analyses(source_file_id)
            self._delete_source_scan_cleanup_artifacts(source_file_id)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise StorageError("Could not update staged source PDF") from exc

        return len(remaining_indices)

    def _validate_requested_tags(self, payload: ImportCommitRequest) -> None:
        requested_tag_ids = {tag_id for document in payload.documents for tag_id in document.tag_ids}
        if not requested_tag_ids:
            return

        tag_stmt = select(Tag.id).where(Tag.id.in_(requested_tag_ids))
        if self.owner_id is not None:
            tag_stmt = tag_stmt.where(Tag.owner_id == self.owner_id)
        found_tag_ids = set(self.db.execute(tag_stmt).scalars().all())
        missing_ids = [str(tag_id) for tag_id in requested_tag_ids if tag_id not in found_tag_ids]
        if missing_ids:
            raise BadRequestError("One or more tags were not found", details={"missing_tag_ids": missing_ids})

    def _validate_requested_correspondents(self, payload: ImportCommitRequest) -> None:
        requested_ids = {
            document.correspondent_id for document in payload.documents if document.correspondent_id is not None
        }
        if not requested_ids:
            return
        corr_stmt = select(Correspondent.id).where(Correspondent.id.in_(requested_ids))
        if self.owner_id is not None:
            corr_stmt = corr_stmt.where(Correspondent.owner_id == self.owner_id)
        found_ids = set(self.db.execute(corr_stmt).scalars().all())
        missing_ids = [str(cid) for cid in requested_ids if cid not in found_ids]
        if missing_ids:
            raise BadRequestError(
                "One or more correspondents were not found",
                details={"missing_correspondent_ids": missing_ids},
            )

    def commit(self, payload: ImportCommitRequest) -> ImportCommitResponse:
        if not payload.documents:
            raise BadRequestError("At least one staging document is required")
        self._validate_requested_tags(payload)
        self._validate_requested_correspondents(payload)

        reader_cache: dict[str, PdfReader] = {}
        created: list[ImportCommitCreatedItem] = []
        errors: list[ImportCommitErrorItem] = []
        source_ids_used: set[str] = set()

        logger.info(
            "import staging commit started documents=%s options=%s",
            len(payload.documents),
            payload.options.model_dump(),
        )

        for document_index, staging_doc in enumerate(payload.documents):
            title = " ".join(staging_doc.title.split()).strip() or "Dokument"
            if not staging_doc.pages:
                errors.append(
                    ImportCommitErrorItem(
                        document_index=document_index,
                        title=title,
                        message="Dokument enthält keine Seiten.",
                    )
                )
                continue

            source_ids_used.update(page.source_file_id for page in staging_doc.pages)

            assembled_path: Path | None = None
            upload_file: _LocalPdfUpload | None = None
            try:
                # Ein manueller Farbmodus ist ein bewusster finaler Override.
                # Er darf nicht unmittelbar danach nochmals von der globalen
                # OCR-Scan-Bereinigung überschrieben werden.
                has_manual_color_mode = any(page.color_mode != "auto" for page in staging_doc.pages)
                scan_cleanup_mode = (
                    "manual"
                    if has_manual_color_mode
                    else self._scan_cleanup_mode_for_committed_pages(staging_doc.pages)
                )
                assembled_path, assembled_page_count = self._build_document_pdf(title, staging_doc.pages, reader_cache)
                upload_file = _LocalPdfUpload(self._safe_document_filename(title), assembled_path)
                created_doc = self.document_service.upload_document(
                    upload_file,
                    document_date=staging_doc.date,
                    notes=staging_doc.note,
                    queue_processing=bool(payload.options.auto_ocr),
                    scan_cleanup_applied=scan_cleanup_mode is not None,
                    scan_cleanup_mode=scan_cleanup_mode,
                )
                if staging_doc.document_type or staging_doc.correspondent_id is not None:
                    if staging_doc.document_type:
                        created_doc.document_type = staging_doc.document_type
                    if staging_doc.correspondent_id is not None:
                        created_doc.correspondent_id = staging_doc.correspondent_id
                    self.document_service.db.commit()
                if staging_doc.tag_ids:
                    self.document_service.replace_document_tags(
                        created_doc.id,
                        DocumentTagReplaceRequest(tag_ids=staging_doc.tag_ids),
                    )
                if staging_doc.retention is not None:
                    try:
                        DocumentRetentionService(self.db, self.owner_id).update_retention(
                            created_doc.id,
                            staging_doc.retention,
                        )
                    except ForbiddenError:
                        # Aufbewahrung in den Einstellungen deaktiviert → still ignorieren.
                        logger.info("skip retention on commit (disabled) doc_id=%s", created_doc.id)
                detail = self.document_service.as_detail(self.document_service.get_document_or_404(created_doc.id))
                created.append(
                    ImportCommitCreatedItem(
                        doc_id=str(created_doc.id),
                        title=detail.display_name or detail.original_filename,
                        page_count=int(detail.page_count or assembled_page_count),
                    )
                )
            except APIError as exc:
                message = exc.message
                if exc.code == "STORAGE_ERROR" and isinstance(exc.details, dict):
                    constraint = str(exc.details.get("constraint") or "").strip()
                    sqlstate = str(exc.details.get("sqlstate") or "").strip()
                    raw_error = str(exc.details.get("error") or "").strip()
                    if constraint:
                        message = f"{message} ({constraint})"
                    elif sqlstate:
                        message = f"{message} (sqlstate={sqlstate})"
                    logger.error(
                        "import staging storage error document_index=%s title=%s constraint=%s sqlstate=%s error=%s",
                        document_index,
                        title,
                        constraint or "-",
                        sqlstate or "-",
                        raw_error or "-",
                    )
                errors.append(
                    ImportCommitErrorItem(
                        document_index=document_index,
                        title=title,
                        message=message,
                    )
                )
            except Exception as exc:
                logger.exception("import staging commit failed document_index=%s title=%s", document_index, title)
                errors.append(
                    ImportCommitErrorItem(
                        document_index=document_index,
                        title=title,
                        message=str(exc) or "Dokument konnte nicht importiert werden.",
                    )
                )
            finally:
                if upload_file is not None:
                    upload_file.close()
                if assembled_path is not None:
                    assembled_path.unlink(missing_ok=True)

        if not errors:
            self._cleanup_source_files(source_ids_used)

        logger.info(
            "import staging commit finished created=%s errors=%s",
            len(created),
            len(errors),
        )
        return ImportCommitResponse(created=created, errors=errors)

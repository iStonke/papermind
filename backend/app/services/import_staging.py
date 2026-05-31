import logging
import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import UploadFile
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import APIError, BadRequestError, PayloadTooLargeError, StorageError
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
from app.services.documents import ALLOWED_PDF_CONTENT_TYPES, DocumentService
from app.services.ocr_pipeline import run_ocr_lite, run_ocr_pipeline
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.import_staging")
settings = get_settings()
_INVALID_TITLE_CHARS = re.compile(r'[\/\\:*?"<>|]+')
_WHITESPACE_RE = re.compile(r"\s+")
_DATE_DMY_RE = re.compile(r"\b([0-3]?\d)[.\-/]([01]?\d)[.\-/]((?:19|20)\d{2})\b")
_DATE_YMD_RE = re.compile(r"\b((?:19|20)\d{2})[.\-/]([01]?\d)[.\-/]([0-3]?\d)\b")
_AMOUNT_RE = re.compile(r"\b\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})\s?(?:€|EUR)?\b", re.IGNORECASE)
_SENDER_LINE_HINTS = ("gmbh", "ag", "kg", "ug", "mbh", "ev", "e.v", "gbr", "ohg", "kasse", "auto-service")
_DOC_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Rechnung", ("rechnung", "invoice", "rechnungsnummer", "gesamtbetrag")),
    ("Quittung", ("quittung", "kassenbon", "bon", "beleg")),
    ("Kündigung", ("kündigung", "kuendigung", "ordentliche kündigung")),
    ("Vertrag", ("vertrag", "vereinbarung", "contract")),
    ("Mahnung", ("mahnung", "zahlungserinnerung", "überfällig", "ueberfaellig")),
    ("Bescheid", ("bescheid", "amt", "behörde", "behoerde")),
    ("Protokoll", ("protokoll", "sitzung", "meeting")),
    ("Brief", ("sehr geehrte", "mit freundlichen grüßen", "mit freundlichen gruessen")),
]
_DOC_TYPES_ALLOWED = {
    "Rechnung",
    "Quittung",
    "Mahnung",
    "Vertrag",
    "Kündigung",
    "Brief",
    "Bescheid",
    "Protokoll",
    "Sonstiges",
}
_FILENAME_SEPARATOR = " – "
_FILENAME_MAX_LEN = 80
_ISSUER_SUFFIX_RE = re.compile(
    r"\b(gmbh|ag|ug|kg|e\.?\s?v\.?|ltd|inc)\b\.?",
    re.IGNORECASE,
)
_TRAILING_PUNCT_RE = re.compile(r"[.,;:\-–\s]+$")
_INVOICE_NO_RE = re.compile(
    r"\b(?:rechnungsnummer|rechnung\s*nr|invoice\s*no|belegnummer|belegnr|rg)\s*[:#-]?\s*([A-Z0-9-]{3,})\b",
    re.IGNORECASE,
)
_CUSTOMER_NO_RE = re.compile(
    r"\b(?:kundennummer|kunden[-\s]?nr|customer\s*id)\s*[:#-]?\s*([A-Z0-9-]{2,})\b",
    re.IGNORECASE,
)
_ISSUER_TOKEN_RE = re.compile(r"[A-Za-zÄÖÜäöüß0-9&.\-]+")
# Tokens that indicate the issuer section has ended (document labels, not company names)
_ISSUER_STOP_TOKENS = frozenset({
    "herr", "frau", "dr", "prof", "an", "z.hd",
    "idnr", "idnr.", "steuernr", "steuernummer", "ustidnr", "ust-id",
    "kundennr", "kundennummer", "auftragsnr", "rechnungsnr",
    "tel", "fax", "postfach", "str", "straße", "strasse", "plz",
    "www", "http", "https", "info@", "kontakt",
})
_LOOSE_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "doc_type": re.compile(r"\b(?:doc_type|doctype|typ|dokumenttyp)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "issuer": re.compile(r"\b(?:issuer|absender|firma|company)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "subject": re.compile(r"\b(?:subject|betreff|thema)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "amount": re.compile(r"\b(?:amount|betrag|summe|gesamtbetrag)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "currency": re.compile(r"\b(?:currency|währung|waehrung)\b\s*[:=]\s*(.+)", re.IGNORECASE),
}
_SUBJECT_HINTS: dict[str, tuple[str, ...]] = {
    "Hauptuntersuchung": ("hauptuntersuchung", "tüv", "tuev", " hu ", "abgas", "au "),
    "Kfz-Service": ("auto-service", "werkstatt", "inspektion", "reparatur", "kfz", "fahrzeug"),
    "Versicherung": ("versicherung", "police", "versicherungsschein"),
    "Vodafone": ("vodafone",),
    "Energie": ("strom", "energie", "gas", "abschlag", "kilowatt"),
    "Kündigung": ("kündigung", "kuendigung"),
}
# Date extraction: prefer dates near contextual keywords
_DATE_CONTEXT_RE = re.compile(
    r"(?:datum|rechnungsdatum|briefdatum|belegdatum|leistungsdatum|"
    r"ausgestellt\s*am|erstellt\s*am|bescheid\s*vom|bescheid\s*für|"
    r"gültig\s*ab|fakturadatum)\s*:?\s*"
    r"([0-3]?\d)[.\-/]([01]?\d)[.\-/]((?:19|20)\d{2})",
    re.IGNORECASE,
)
# Subject heading patterns: (pattern, extractor_fn)
_SUBJECT_HEADING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(Einkommensteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Lohnsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Umsatzsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Körperschaftsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Gewerbesteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Grundsteuer(?:bescheid)?)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Rentenbescheid|Renteninformation)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Jahresabrechnung)\s+((?:19|20)\d{2})\b", re.IGNORECASE), "{0} {1}"),
    (re.compile(r"\b(Kontoauszug)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Kreditkartenabrechnung)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Gehaltsabrechnung|Lohnabrechnung|Gehaltsnachweis)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Nebenkostenabrechnung|Betriebskostenabrechnung)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Versicherungsschein|Police)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Mietvertrag)\b", re.IGNORECASE), "{0}"),
    (re.compile(r"\b(Arbeitsvertrag)\b", re.IGNORECASE), "{0}"),
]
# Tag rules: list of (keywords_in_text, tags_to_apply)
_TAG_KEYWORD_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("einkommensteuer",), ["Einkommensteuer", "Steuer"]),
    (("lohnsteuer",), ["Lohnsteuer", "Steuer"]),
    (("umsatzsteuer",), ["Umsatzsteuer", "Steuer"]),
    (("körperschaftsteuer", "koerperschaftsteuer"), ["Körperschaftsteuer", "Steuer"]),
    (("gewerbesteuer",), ["Gewerbesteuer", "Steuer"]),
    (("grundsteuer",), ["Grundsteuer", "Steuer"]),
    (("kindergeld",), ["Kindergeld"]),
    (("rentenbescheid", "renteninformation", "rentenversicherung"), ["Rente", "Rentenversicherung"]),
    (("krankenversicherung", "gesundheitsversicherung"), ["Krankenversicherung", "Gesundheit"]),
    (("pflegeversicherung",), ["Pflegeversicherung"]),
    (("unfallversicherung",), ["Unfallversicherung"]),
    (("haftpflichtversicherung", "haftpflicht"), ["Haftpflicht", "Versicherung"]),
    (("kfz-versicherung", "kraftfahrzeugversicherung", "fahrzeugversicherung"), ["KFZ-Versicherung", "Auto"]),
    (("lebensversicherung",), ["Lebensversicherung"]),
    (("strom", "stromverbrauch", "kilowattstunde", "kwh"), ["Strom", "Energie"]),
    (("gasverbrauch", "erdgas", "gasversorger"), ["Gas", "Energie"]),
    (("wasserverbrauch", "trinkwasser", "abwasser"), ["Wasser"]),
    (("fernwärme", "heizung", "heizkosten"), ["Heizung", "Energie"]),
    (("internetanschluss", "internettarif", "dsl", "breitband", "glasfaser"), ["Internet", "Telekommunikation"]),
    (("mobilfunk", "handy", "smartphone", "vodafone", "telekom", "o2 ", "congstar"), ["Mobilfunk", "Telekommunikation"]),
    (("festnetz", "telefon"), ["Telefon", "Telekommunikation"]),
    (("miete", "mietvertrag", "kaltmiete", "warmmiete"), ["Miete", "Wohnen"]),
    (("nebenkosten", "betriebskosten", "hausgeld"), ["Nebenkosten", "Wohnen"]),
    (("arzt", "praxis", "behandlung", "untersuchung", "osteopathie", "physiotherapie", "zahnarzt", "orthopädie"), ["Arzt", "Gesundheit"]),
    (("apotheke", "medikament", "rezept"), ["Apotheke", "Gesundheit"]),
    (("krankenhaus", "klinik", "station"), ["Krankenhaus", "Gesundheit"]),
    (("gehaltsabrechnung", "lohnabrechnung", "gehaltsnachweis", "entgeltabrechnung"), ["Gehalt", "Arbeit"]),
    (("arbeitsvertrag",), ["Arbeitsvertrag", "Arbeit"]),
    (("kündigung",), ["Kündigung"]),
    (("mietvertrag",), ["Mietvertrag", "Wohnen"]),
    (("kontoauszug", "kontoumsätze"), ["Kontoauszug", "Bank"]),
    (("kreditkarte", "kreditkartenabrechnung"), ["Kreditkarte", "Bank"]),
    (("darlehen", "kredit", "tilgung", "zinsen"), ["Kredit", "Bank"]),
    (("depot", "wertpapier", "aktie", "fonds"), ["Geldanlage", "Bank"]),
    (("finanzamt",), ["Finanzamt", "Steuer"]),
]


class _LocalPdfUpload:
    def __init__(self, filename: str, source_path: Path) -> None:
        self.filename = filename
        self.content_type = "application/pdf"
        self.file = source_path.open("rb")

    def close(self) -> None:
        self.file.close()


class ImportStagingService:
    def __init__(self, db: Session):
        self.db = db
        self.document_service = DocumentService(db)
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

    def get_source_pdf_path(self, source_file_id: str) -> Path:
        source_path = self._source_pdf_path(source_file_id)
        if not source_path.exists() or not source_path.is_file():
            raise BadRequestError("Staging source PDF not found", details={"source_file_id": source_file_id})
        return source_path

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
            original_name = self._validate_source_file(file)
            source_file_id = str(uuid.uuid4())
            source_path = self._source_pdf_path(source_file_id)

            try:
                self._store_source_pdf(file, source_path)
                reader = PdfReader(str(source_path))
                page_count = len(reader.pages)
                if page_count <= 0:
                    raise BadRequestError("Uploaded PDF has no pages", details={"filename": original_name})
            except Exception:
                source_path.unlink(missing_ok=True)
                raise

            items.append(
                ImportSourceRead(
                    source_file_id=source_file_id,
                    original_name=original_name,
                    page_count=page_count,
                )
            )

        return ImportSourceUploadResponse(items=items)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return _WHITESPACE_RE.sub(" ", str(value or "")).strip()

    def _extract_text_for_title_suggestion(
        self,
        source_file_ids: list[str],
        *,
        page_scope: str,
        max_pages: int = 5,
        max_chars: int = 12000,
    ) -> tuple[str, int, list[str]]:
        normalized_ids = []
        seen = set()
        for source_file_id in source_file_ids:
            value = str(source_file_id or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized_ids.append(value)
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

    def _extract_text_with_ocr_fallback(self, source_file_ids: list[str], *, page_scope: str) -> str:
        """OCR fallback using the lightweight run_ocr_lite path.

        Skips ocrmypdf and heavy NlMeans denoising — only pdfium + CLAHE/Otsu + Tesseract.
        This reduces per-page time from minutes to ~2-6 seconds.
        """
        normalized_ids = [str(sid or "").strip() for sid in source_file_ids if str(sid or "").strip()]
        if not normalized_ids:
            return ""

        ocr_settings = self.settings_service.get_settings().model_dump(mode="json").get("ocr", {})
        language = str(ocr_settings.get("language") or "deu+eng")
        max_sources = 1 if page_scope == "first_page" else 2
        max_pages_per_source = 1 if page_scope == "first_page" else 3
        captured_texts: list[str] = []

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
                try:
                    text = run_ocr_lite(source_path, page_index=page_idx, language=language)
                    normalized = self._normalize_text(text)
                    if normalized:
                        source_texts.append(normalized)
                except Exception as exc:
                    logger.warning(
                        "stage title ocr lite failed source_file_id=%s page=%s err=%s",
                        source_file_id, page_idx, exc,
                    )

            if source_texts:
                captured_texts.extend(source_texts)
                if page_scope == "first_page":
                    break

        return self._normalize_text("\n\n".join(captured_texts))

    @staticmethod
    def _detect_document_type(text_value: str) -> str:
        normalized = str(text_value or "").lower()
        if any(token in normalized for token in ("rechnung", "invoice", "rechnungsnr", "rechnungsnummer", "rg ")):
            return "Rechnung"
        for doc_type, keywords in _DOC_TYPE_KEYWORDS:
            if any(keyword in normalized for keyword in keywords):
                return doc_type
        return "Sonstiges"

    @staticmethod
    def _normalize_doc_type(value: str | None) -> str | None:
        normalized = ImportStagingService._normalize_text(value or "")
        if not normalized:
            return None
        if normalized in _DOC_TYPES_ALLOWED:
            return normalized
        lower = normalized.lower()
        for doc_type, keywords in _DOC_TYPE_KEYWORDS:
            if doc_type.lower() in lower or any(keyword in lower for keyword in keywords):
                return doc_type
        return None

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
        normalized = ImportStagingService._clean_filename_component(value, max_len=40)
        normalized = normalized.replace(" - ", " ").replace(" – ", " ")
        normalized = _ISSUER_SUFFIX_RE.sub("", normalized)
        normalized = _TRAILING_PUNCT_RE.sub("", normalized).strip()
        if len(normalized) > 30:
            normalized = normalized[:30].rstrip(" .,-")
        return normalized

    @staticmethod
    def _extract_issuer_from_line(line: str) -> str:
        compact = ImportStagingService._normalize_text(line)
        if not compact:
            return ""

        head = compact.split(",")[0].strip()
        if not head:
            head = compact
        head = re.sub(r"^[^A-Za-zÄÖÜäöüß0-9]+", "", head).strip()
        if not head:
            return ""

        # Collapse duplicated leading token groups, e.g. "Firma Firma, ..."
        head_tokens = head.split()
        if len(head_tokens) >= 2:
            max_group = len(head_tokens) // 2
            for group_size in range(max_group, 0, -1):
                left = head_tokens[:group_size]
                right = head_tokens[group_size : group_size * 2]
                if left == right:
                    head = " ".join(left)
                    break

        tokens = _ISSUER_TOKEN_RE.findall(head)
        cleaned_tokens: list[str] = []
        for token in tokens:
            lowered = token.lower().rstrip(".")
            if not re.search(r"[a-zäöüß0-9]", lowered):
                continue
            if lowered in _ISSUER_STOP_TOKENS:
                break
            if re.fullmatch(r"\d+[a-zA-Z]?", token):
                break
            cleaned_tokens.append(token)
            if len(cleaned_tokens) >= 6:
                break

        candidate = " ".join(cleaned_tokens).strip()
        return ImportStagingService._normalize_issuer(candidate)

    @staticmethod
    def _normalize_subject(value: str) -> str:
        normalized = ImportStagingService._clean_filename_component(value, max_len=60)
        normalized = normalized.replace(" - ", " ").replace(" – ", " ")
        normalized = re.sub(r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\b", "", normalized)
        normalized = re.sub(r"\b(?:rechnungsnummer|rechnung\s*nr|invoice\s*no|belegnummer|belegnr)\b.*$", "", normalized, flags=re.IGNORECASE)
        normalized = _WHITESPACE_RE.sub(" ", normalized).strip(" .,-_")
        if len(normalized) > 40:
            normalized = normalized[:40].rstrip(" .,-_")
        return normalized

    @staticmethod
    def _detect_sender(text_value: str) -> str | None:
        lines = [line.strip() for line in str(text_value or "").splitlines() if line.strip()]
        if not lines:
            return None
        candidates = lines[:20]
        for line in candidates:
            normalized = line.lower()
            if any(hint in normalized for hint in _SENDER_LINE_HINTS):
                issuer = ImportStagingService._extract_issuer_from_line(line)
                return issuer or None
        for line in candidates:
            if 2 <= len(line.split()) <= 6 and len(line) <= 44 and not any(char.isdigit() for char in line):
                issuer = ImportStagingService._normalize_issuer(line)
                return issuer or None
        for line in candidates[:8]:
            issuer = ImportStagingService._extract_issuer_from_line(line)
            if not issuer:
                continue
            lowered = issuer.lower()
            if lowered in {"herr", "frau"}:
                continue
            if re.search(r"\b\d{3,}\b", issuer):
                continue
            if len(issuer) < 4:
                continue
            return issuer
        return None

    @staticmethod
    def _detect_amount_currency(text_value: str) -> tuple[float | None, str | None]:
        source = str(text_value or "")
        matches = list(_AMOUNT_RE.finditer(source))
        if not matches:
            return None, None
        prioritized = None
        for match in matches:
            start = max(0, match.start() - 28)
            end = min(len(source), match.end() + 28)
            window = source[start:end].lower()
            if any(key in window for key in ("gesamt", "summe", "total", "endbetrag", "brutto")):
                prioritized = match
        chosen = prioritized or matches[-1]
        token = chosen.group(0).replace(" ", "")
        currency = "EUR" if ("€" in token or "eur" in token.lower()) else None
        numeric = re.sub(r"[^0-9,.-]", "", token)
        numeric = numeric.replace(".", "").replace(",", ".")
        try:
            amount = round(float(numeric), 2)
        except ValueError:
            return None, currency
        if amount <= 0:
            return None, None
        return amount, currency

    @staticmethod
    def _detect_subject_heuristic(text_value: str) -> str:
        normalized = f" {str(text_value or '').lower()} "
        if any(token in normalized for token in _SUBJECT_HINTS["Hauptuntersuchung"]):
            return "Hauptuntersuchung"
        if any(token in normalized for token in _SUBJECT_HINTS["Kfz-Service"]):
            return "Kfz-Service"
        if "versicherung" in normalized:
            return "Versicherung"
        if "vodafone" in normalized:
            return "Vodafone"
        if any(token in normalized for token in _SUBJECT_HINTS["Energie"]):
            return "Energie"
        if "kündigung" in normalized or "kuendigung" in normalized:
            return "Kündigung"
        return "Ohne Betreff"

    @staticmethod
    def _is_subject_supported_by_context(subject: str, text_value: str, issuer_value: str = "") -> bool:
        normalized_subject = ImportStagingService._normalize_subject(subject).lower()
        if not normalized_subject:
            return False
        if len(normalized_subject.split()) > 5:
            return False
        context = f" {str(text_value or '').lower()} {str(issuer_value or '').lower()} "
        known = {key.lower(): key for key in _SUBJECT_HINTS}
        if normalized_subject in known:
            return any(token in context for token in _SUBJECT_HINTS[known[normalized_subject]])
        if normalized_subject == "ohne betreff":
            return False
        return True

    @classmethod
    def _sanitize_title(cls, value: str, *, fallback: str | None = None, max_len: int = _FILENAME_MAX_LEN) -> str:
        sanitized = _INVALID_TITLE_CHARS.sub(" ", str(value or ""))
        sanitized = _WHITESPACE_RE.sub(" ", sanitized).strip(" .-_")
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len].rstrip(" .-_")
        if sanitized:
            return sanitized
        if fallback:
            return cls._sanitize_title(fallback, fallback=None)
        return f"Scan - {datetime.utcnow().date().isoformat()}"

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
        today = datetime.utcnow().strftime("%d-%m-%Y")
        combinations = [
            [doc_type, sender, date_value],
            [doc_type, sender, f"{amount:.2f}{currency or ''}" if isinstance(amount, float) else None],
            [doc_type, sender],
            [doc_type, date_value],
            [f"Scan - {today}"],
        ]
        for parts in combinations:
            filtered = [cls._sanitize_title(part) for part in parts if str(part or "").strip()]
            if filtered:
                candidate = _FILENAME_SEPARATOR.join(filtered)
                return cls._sanitize_title(candidate, max_len=_FILENAME_MAX_LEN)
        return f"Scan - {today}"

    @classmethod
    def _extract_json_object(cls, value: str) -> dict[str, object] | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        candidate = raw
        if not (candidate.startswith("{") and candidate.endswith("}")):
            match = re.search(r"\{[\s\S]*\}", candidate)
            if not match:
                return None
            candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    @classmethod
    def _extract_loose_fields(cls, raw_text: str) -> dict[str, object] | None:
        lines = [cls._normalize_text(line) for line in str(raw_text or "").splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return None

        extracted: dict[str, object] = {}
        for key, pattern in _LOOSE_FIELD_PATTERNS.items():
            value = ""
            for line in lines:
                match = pattern.search(line)
                if match:
                    value = cls._normalize_text(match.group(1))
                    break
            if not value:
                continue
            extracted[key] = value

        if not extracted:
            return None
        return extracted

    @staticmethod
    def _safe_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return round(float(str(value).replace(",", ".")), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_document_date(text: str) -> str | None:
        """Extract the most relevant document date from OCR text. Returns ISO string YYYY-MM-DD or None."""
        # 1st priority: date immediately after a context keyword
        match = _DATE_CONTEXT_RE.search(text)
        if match:
            try:
                d = datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
                return d.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # 2nd priority: first plausible date found in the document
        for m in _DATE_DMY_RE.finditer(text):
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                d = datetime(year, month, day)
                if 2000 <= year <= 2099:
                    return d.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # 3rd priority: ISO date (YYYY-MM-DD)
        for m in _DATE_YMD_RE.finditer(text):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                d = datetime(year, month, day)
                if 2000 <= year <= 2099:
                    return d.strftime("%Y-%m-%d")
            except ValueError:
                pass

        return None

    @staticmethod
    def _detect_document_type_improved(text: str) -> str:
        """Word-boundary-aware doc type detection that avoids common false positives."""
        lower = text.lower()
        # High-confidence Bescheid indicators — check BEFORE Rechnung
        if re.search(r"\b(bescheid|finanzamt|steuerbescheid|einkommensteuer|lohnsteuer|umsatzsteuer"
                     r"|grundsteuer|gewerbesteuer|rentenbescheid|bewilligungsbescheid"
                     r"|widerspruchsbescheid|ablehnungsbescheid|anerkennungsbescheid)\b", lower):
            return "Bescheid"
        # Word-boundary Rechnung (avoids "Abrechnung", "Jahresabrechnung" etc.)
        if re.search(r"\brechnung\b|\binvoice\b|\brechnungsnr\b|\brechnungsnummer\b", lower):
            return "Rechnung"
        # Remaining doc types in priority order
        for doc_type, keywords in _DOC_TYPE_KEYWORDS:
            if doc_type in {"Rechnung", "Bescheid"}:
                continue  # already handled above
            if any(keyword in lower for keyword in keywords):
                return doc_type
        return "Sonstiges"

    @staticmethod
    def _extract_subject_rich(text: str, doc_type: str) -> str | None:
        """Extract a meaningful subject/heading from OCR text."""
        lower = text.lower()
        # Tax terms checked first so we use the clean embedded label, not OCR artifacts
        tax_terms = [
            ("einkommensteuer", "Einkommensteuer"),
            ("lohnsteuer", "Lohnsteuer"),
            ("umsatzsteuer", "Umsatzsteuer"),
            ("körperschaftsteuer", "Körperschaftsteuer"),
            ("koerperschaftsteuer", "Körperschaftsteuer"),
            ("gewerbesteuer", "Gewerbesteuer"),
            ("grundsteuer", "Grundsteuer"),
        ]
        for kw, label in tax_terms:
            if kw in lower:
                # Prefer explicit "für YEAR" / "Steuerjahr YEAR" context
                ym = re.search(
                    r"\b(?:f[üu]r|steuerjahr|est|zur|jahr)\s+(20\d{2})\b",
                    text, re.IGNORECASE,
                )
                if not ym:
                    ym = re.search(r"\b(20\d{2})\b", text)
                if ym:
                    return f"{label} {ym.group(1)}"
                return label

        # "Bescheid für YEAR über <SteuerArt>" — fallback when no clean term found
        m = re.search(
            r"\bbescheid\s+f[üu]r\s+(20\d{2})\s+[üu]ber\s+([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\- ]{4,30})",
            text, re.IGNORECASE,
        )
        if m:
            year = m.group(1)
            raw_type = " ".join(m.group(2).split())[:30].strip()
            # Collapse spaced OCR artifacts ("E i n k o m m e n s t e u e r" → "Einkommensteuer")
            if re.fullmatch(r"(?:[A-Za-zÄÖÜäöüß] +){3,}[A-Za-zÄÖÜäöüß]", raw_type):
                raw_type = re.sub(r"\s+", "", raw_type)
            return f"{raw_type} {year}"

        # Fixed-label heading patterns
        for pattern, fmt in _SUBJECT_HEADING_PATTERNS:
            m = pattern.search(text)
            if m:
                groups = [m.group(i + 1) for i in range(len(m.groups()))]
                return fmt.format(*groups)

        return None

    @classmethod
    def _generate_tags_from_text(cls, text: str, doc_type: str) -> list[str]:
        """Generate up to 3 relevant tags from OCR text using keyword rules."""
        # Strip URLs and email addresses to avoid false positives from footers
        clean = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", text, flags=re.IGNORECASE)
        lower = clean.lower()
        tags: list[str] = []
        seen: set[str] = set()
        for keywords, tag_list in _TAG_KEYWORD_RULES:
            # Use word-boundary matching to avoid substring false positives
            # e.g. "lohn" in "Bruttoarbeitslohn" should not trigger "Gehalt"
            matched = any(
                re.search(r"\b" + re.escape(kw) + r"\b", lower)
                for kw in keywords
            )
            if matched:
                for tag in tag_list:
                    if tag not in seen and len(tags) < 3:
                        seen.add(tag)
                        tags.append(tag)
            if len(tags) >= 3:
                break
        return tags

    @staticmethod
    def _call_ollama_for_staging(
        ocr_text: str,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_input_chars: int,
        existing_tags: list[str] | None = None,
    ) -> dict[str, object] | None:
        """Call Ollama to extract metadata from OCR text.

        Returns a dict with doc_type, issuer, subject, date, tags, amount, currency
        or None if Ollama is unreachable or returns an unparseable response.
        Text is truncated to max_input_chars before sending.

        existing_tags steuert die Tag-Vergabe: das Modell soll – wenn inhaltlich
        passend – vorhandene Tags wiederverwenden statt neue Varianten zu erfinden.
        """
        text_for_llm = " ".join(str(ocr_text or "").split())[:max_input_chars]
        if not text_for_llm:
            return None

        tag_names = [str(n).strip() for n in (existing_tags or []) if str(n).strip()]
        tag_hint = ""
        if tag_names:
            tag_hint = (
                '\nWICHTIG für "tags": Bevorzuge – wenn inhaltlich passend – diese bereits '
                "vorhandenen Tags und schreibe sie EXAKT so: "
                + ", ".join(tag_names[:60])
                + ". Erfinde nur dann ein neues Tag, wenn inhaltlich keines davon passt.\n"
            )

        prompt = (
            "Extrahiere aus dem folgenden OCR-Text eines deutschen Dokuments die Metadaten. "
            "Antworte NUR mit einem gültigen JSON-Objekt, ohne Markdown, ohne Erklärungen.\n\n"
            "Felder:\n"
            '- "doc_type": eines von [Rechnung, Quittung, Mahnung, Vertrag, Kündigung, Brief, Bescheid, Protokoll, Sonstiges]\n'
            '- "issuer": Absender/Aussteller, max. 40 Zeichen, oder null\n'
            '- "subject": Dokumentthema als kurzer Ausdruck, max. 50 Zeichen, oder null\n'
            '- "date": Dokumentdatum als YYYY-MM-DD oder null\n'
            '- "tags": Array mit 1–3 deutschen Schlagworten oder []\n'
            '- "amount": Gesamtbetrag als Zahl (z.B. 123.45) oder null\n'
            '- "currency": "EUR" oder null\n'
            + tag_hint
            + f"\nOCR-Text:\n{text_for_llm}"
        )
        payload = {"model": model, "stream": False, "format": "json", "prompt": prompt}

        try:
            response = httpx.post(
                f"{base_url.rstrip('/')}/api/generate",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            raw = str(response.json().get("response") or "").strip()
        except Exception as exc:
            logger.warning("ollama staging call failed: %s", exc)
            return None

        if not raw:
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
            v = " ".join(str(parsed.get(key) or "").split()).strip()
            return v[:max_len] if v else None

        def _date(key: str) -> str | None:
            v = str(parsed.get(key) or "").strip()
            return v if re.match(r"^\d{4}-\d{2}-\d{2}$", v) else None

        def _tags(key: str) -> list[str]:
            raw_tags = parsed.get(key)
            if not isinstance(raw_tags, list):
                return []
            return [str(t).strip() for t in raw_tags if str(t).strip()][:3]

        def _amount(key: str) -> float | None:
            try:
                v = float(str(parsed.get(key) or "").replace(",", "."))
                return round(v, 2) if v > 0 else None
            except (TypeError, ValueError):
                return None

        return {
            "doc_type": _str("doc_type", 40),
            "issuer": _str("issuer", 40),
            "subject": _str("subject", 50),
            "date": _date("date"),
            "tags": _tags("tags"),
            "amount": _amount("amount"),
            "currency": "EUR" if str(parsed.get("currency") or "").upper() == "EUR" else None,
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
            "- tags: Liste von 1-3 kurzen Schlagworten als Strings (z.B. [\"Strom\", \"Stadtwerke\"]) oder []\n\n"
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
            [str(t).strip() for t in tags_raw if t and str(t).strip()][:3]
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

    _DOC_TYPE_TO_CATEGORY: dict[str, str] = {
        "Rechnung": "Rechnungen",
        "Quittung": "Belege",
        "Mahnung": "Rechnungen",
        "Vertrag": "Verträge",
        "Kündigung": "Verträge",
        "Brief": "Briefe",
        "Bescheid": "Briefe",
        "Protokoll": "Briefe",
    }

    @classmethod
    def _map_doc_type_to_category(cls, doc_type: str) -> str | None:
        return cls._DOC_TYPE_TO_CATEGORY.get(str(doc_type or "").strip())

    @classmethod
    def _format_euro(cls, amount: float) -> str:
        token = f"{amount:.2f}".replace(".", ",")
        return f"{token}€"

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
        doc_type = cls._clean_filename_component(str(meta.get("doc_type") or "Dokument"), max_len=24) or "Dokument"
        issuer = cls._normalize_issuer(str(meta.get("issuer") or "")) or "Unbekannt"
        subject = cls._normalize_subject(str(meta.get("subject") or "")) or "Ohne Betreff"
        amount_value = cls._safe_float(meta.get("amount"))

        base_parts = [doc_type, issuer, subject]
        base = _FILENAME_SEPARATOR.join(base_parts)
        if amount_value is not None:
            filename = f"{base}{_FILENAME_SEPARATOR}{cls._format_euro(amount_value)}"
        else:
            filename = base

        filename = cls._clean_filename_component(filename, max_len=_FILENAME_MAX_LEN + 20)
        filename = filename.replace(" - ", _FILENAME_SEPARATOR)
        if len(filename) <= _FILENAME_MAX_LEN:
            return filename

        # 1) shorten subject, 2) shorten issuer, never shorten doc_type/amount
        short_subject = cls._clip_with_ellipsis(subject, 28)
        base = _FILENAME_SEPARATOR.join([doc_type, issuer, short_subject])
        filename = f"{base}{_FILENAME_SEPARATOR}{cls._format_euro(amount_value)}" if amount_value is not None else base
        filename = cls._clean_filename_component(filename, max_len=_FILENAME_MAX_LEN + 20).replace(" - ", _FILENAME_SEPARATOR)
        if len(filename) <= _FILENAME_MAX_LEN:
            return filename

        short_issuer = cls._clip_with_ellipsis(issuer, 24)
        base = _FILENAME_SEPARATOR.join([doc_type, short_issuer, short_subject])
        filename = f"{base}{_FILENAME_SEPARATOR}{cls._format_euro(amount_value)}" if amount_value is not None else base
        return cls._clean_filename_component(filename, max_len=_FILENAME_MAX_LEN).replace(" - ", _FILENAME_SEPARATOR)

    def _load_existing_tag_names(self, limit: int = 200) -> list[str]:
        """Vorhandene Tag-Namen für die KI-Tag-Vergabe (bevorzugt wiederverwenden)."""
        try:
            rows = self.db.execute(select(Tag.name).order_by(Tag.name).limit(limit)).scalars().all()
        except Exception as exc:  # noqa: BLE001 - best effort, darf die Erkennung nie blockieren
            logger.warning("stage title: could not load existing tags: %s", exc)
            return []
        return [str(name).strip() for name in rows if name and str(name).strip()]

    def suggest_stage_title(
        self,
        source_file_ids: list[str],
        *,
        page_scope: str = "first_page",
        stage_id: str | None = None,
    ) -> dict[str, object]:
        normalized_scope = str(page_scope or "first_page").strip().lower()
        if normalized_scope not in {"first_page", "all_pages"}:
            raise BadRequestError("pageScope must be first_page or all_pages")

        extracted_text, _pages_scanned, page_refs = self._extract_text_for_title_suggestion(
            source_file_ids,
            page_scope=normalized_scope,
            max_pages=5 if normalized_scope == "all_pages" else 1,
            max_chars=12000,
        )
        ocr_pending = False
        if not extracted_text:
            extracted_text = self._extract_text_with_ocr_fallback(source_file_ids, page_scope=normalized_scope)
            if len(extracted_text) > 12000:
                extracted_text = extracted_text[:12000].rstrip()
            if not extracted_text:
                ocr_pending = True

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
        today_filename = datetime.utcnow().strftime("%d-%m-%Y")
        today_display = datetime.utcnow().strftime("%d.%m.%Y")
        if ocr_pending:
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
                    "category": None,
                    "tags": [],
                },
            }

        if len(extracted_text.strip()) < 80:
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
                    "category": None,
                    "tags": [],
                },
            }

        # Try Ollama first if configured, fall back to rule-based extraction.
        runtime_settings = self.settings_service.get_settings().model_dump(mode="json")
        ollama_cfg = runtime_settings.get("ollama") or {}
        existing_tag_names = self._load_existing_tag_names()
        ollama_rich: dict[str, object] | None = None
        if ollama_cfg.get("enabled"):
            ollama_rich = self._call_ollama_for_staging(
                extracted_text,
                base_url=str(ollama_cfg.get("base_url") or "http://localhost:11434"),
                model=str(ollama_cfg.get("model") or "llama3.2:3b"),
                timeout_seconds=float(ollama_cfg.get("timeout_seconds") or 90.0),
                max_input_chars=int(ollama_cfg.get("max_input_chars") or 800),
                existing_tags=existing_tag_names,
            )
            if ollama_rich:
                logger.info("SuggestTitle: ollama extraction succeeded stage=%s", str(stage_id or "").strip() or "-")

        rule_rich = self._extract_rich_metadata(extracted_text)
        # Merge: Ollama wins on fields it provided, rule-based fills remaining gaps
        if ollama_rich:
            rich: dict[str, object] = {
                "doc_type": ollama_rich.get("doc_type") or rule_rich.get("doc_type"),
                "issuer": ollama_rich.get("issuer") or rule_rich.get("issuer"),
                "subject": ollama_rich.get("subject") or rule_rich.get("subject"),
                "date": ollama_rich.get("date") or rule_rich.get("date"),
                "tags": ollama_rich.get("tags") or rule_rich.get("tags") or [],
                "amount": ollama_rich.get("amount") if ollama_rich.get("amount") is not None else rule_rich.get("amount"),
                "currency": ollama_rich.get("currency") or rule_rich.get("currency"),
            }
        else:
            rich = rule_rich

        normalized_doc_type = self._normalize_doc_type(str(rich.get("doc_type") or "")) or "Sonstiges"
        issuer = self._normalize_issuer(str(rich.get("issuer") or "")) or "Unbekannt"
        subject = self._normalize_subject(str(rich.get("subject") or "")) or None
        normalized_amount = self._safe_float(rich.get("amount"))
        if normalized_amount is not None and normalized_amount <= 0:
            normalized_amount = None
        currency = "EUR" if (normalized_amount is not None) else None
        raw_date = str(rich.get("date") or "").strip()
        final_date = raw_date if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date) else None
        tags_val = rich.get("tags")
        final_tags: list[str] = (
            [str(t).strip() for t in tags_val if t and str(t).strip()][:3]
            if isinstance(tags_val, list)
            else []
        )
        # Auf vorhandene Schreibweise einrasten: stimmt ein Tag (unabhängig von
        # Groß-/Kleinschreibung und Randleerzeichen) mit einem bestehenden Tag
        # überein, exakt dessen Schreibweise verwenden. Verhindert Casing-Duplikate
        # und sorgt dafür, dass das Frontend das vorhandene Tag wiederverwendet.
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

        merged_meta: dict[str, object] = {
            "doc_type": normalized_doc_type,
            "issuer": issuer,
            "subject": subject or "Ohne Betreff",
            "amount": normalized_amount,
            "currency": currency,
        }
        suggestion = self._build_filename_from_meta(merged_meta)

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
                "category": self._map_doc_type_to_category(normalized_doc_type),
                "tags": final_tags,
            },
        }

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
        return True

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
            reader = self._load_source_reader(page.source_file_id, reader_cache)
            if page.page_index >= len(reader.pages):
                raise BadRequestError(
                    "page_index is out of range",
                    details={
                        "source_file_id": page.source_file_id,
                        "page_index": page.page_index,
                        "max_page_index": len(reader.pages) - 1,
                    },
                )
            writer.add_page(reader.pages[page.page_index])
            if page.rotation:
                writer.pages[-1].rotate(page.rotation)

        if len(writer.pages) <= 0:
            raise BadRequestError("Document has no pages")

        with assembled_path.open("wb") as output:
            writer.write(output)

        return assembled_path, len(writer.pages)

    def _cleanup_source_files(self, source_file_ids: set[str]) -> None:
        for source_file_id in source_file_ids:
            try:
                source_path = self._source_pdf_path(source_file_id)
            except BadRequestError:
                continue
            source_path.unlink(missing_ok=True)

    def delete_source_file(self, source_file_id: str) -> None:
        source_path = self._source_pdf_path(source_file_id)
        try:
            source_path.unlink(missing_ok=True)
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
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            raise StorageError("Could not update staged source PDF") from exc

        return len(remaining_indices)

    def _validate_requested_tags(self, payload: ImportCommitRequest) -> None:
        requested_tag_ids = {tag_id for document in payload.documents for tag_id in document.tag_ids}
        if not requested_tag_ids:
            return

        found_tag_ids = set(self.db.execute(select(Tag.id).where(Tag.id.in_(requested_tag_ids))).scalars().all())
        missing_ids = [str(tag_id) for tag_id in requested_tag_ids if tag_id not in found_tag_ids]
        if missing_ids:
            raise BadRequestError("One or more tags were not found", details={"missing_tag_ids": missing_ids})

    def commit(self, payload: ImportCommitRequest) -> ImportCommitResponse:
        if not payload.documents:
            raise BadRequestError("At least one staging document is required")
        self._validate_requested_tags(payload)

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
                assembled_path, assembled_page_count = self._build_document_pdf(title, staging_doc.pages, reader_cache)
                upload_file = _LocalPdfUpload(self._safe_document_filename(title), assembled_path)
                created_doc = self.document_service.upload_document(upload_file, document_date=None, notes=None)
                if staging_doc.tag_ids:
                    self.document_service.replace_document_tags(
                        created_doc.id,
                        DocumentTagReplaceRequest(tag_ids=staging_doc.tag_ids),
                    )
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

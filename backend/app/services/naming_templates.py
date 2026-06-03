import re
from datetime import date, datetime
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document_type import DocumentType


_FILENAME_SEPARATOR = " – "
_FILENAME_MAX_LEN = 80
_INVALID_TITLE_CHARS = re.compile(r'[\/\\:*?"<>|]+')
_WHITESPACE_RE = re.compile(r"\s+")
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^{}]+))?\}")
_ISSUER_SUFFIX_RE = re.compile(
    r"\b(gmbh|ag|ug|kg|e\.?\s?v\.?|ltd|inc)\b\.?",
    re.IGNORECASE,
)
_TRAILING_PUNCT_RE = re.compile(r"[.,;:\-–\s]+$")


FallbackBuilder = Callable[[dict[str, object]], str]


def _clean_filename_component(value: str, *, max_len: int = 80) -> str:
    text = _INVALID_TITLE_CHARS.sub(" ", str(value or ""))
    text = text.replace("\u00a0", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip(" .-_")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .-_")
    return text


def _normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _normalize_issuer(value: str) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    text = _TRAILING_PUNCT_RE.sub("", text)
    text = _ISSUER_SUFFIX_RE.sub(lambda match: match.group(1).upper().replace("E.V", "e.V"), text)
    text = _clean_filename_component(text, max_len=60)
    return text or None


def _normalize_subject(value: str) -> str | None:
    text = _clean_filename_component(_normalize_text(value), max_len=70)
    return text or None


def _safe_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _format_euro(amount: float) -> str:
    token = f"{amount:.2f}".replace(".", ",")
    return f"{token}€"


def _clip_with_ellipsis(value: str, max_len: int) -> str:
    normalized = _clean_filename_component(value, max_len=max_len + 8)
    if len(normalized) <= max_len:
        return normalized
    if max_len <= 1:
        return normalized[:max_len]
    return f"{normalized[: max_len - 1].rstrip()}…"


def build_legacy_filename_from_meta(meta: dict[str, object]) -> str:
    """Bisheriges festes Schema als stabiler Fallback."""
    doc_type = _clean_filename_component(str(meta.get("doc_type") or "Dokument"), max_len=24) or "Dokument"
    issuer = _normalize_issuer(str(meta.get("issuer") or "")) or "Unbekannt"
    subject = _normalize_subject(str(meta.get("subject") or "")) or "Ohne Betreff"
    amount_value = _safe_float(meta.get("amount"))

    base_parts = [doc_type, issuer, subject]
    base = _FILENAME_SEPARATOR.join(base_parts)
    if amount_value is not None:
        filename = f"{base}{_FILENAME_SEPARATOR}{_format_euro(amount_value)}"
    else:
        filename = base

    filename = _clean_filename_component(filename, max_len=_FILENAME_MAX_LEN + 20)
    filename = filename.replace(" - ", _FILENAME_SEPARATOR)
    if len(filename) <= _FILENAME_MAX_LEN:
        return filename

    short_subject = _clip_with_ellipsis(subject, 28)
    base = _FILENAME_SEPARATOR.join([doc_type, issuer, short_subject])
    filename = f"{base}{_FILENAME_SEPARATOR}{_format_euro(amount_value)}" if amount_value is not None else base
    filename = _clean_filename_component(filename, max_len=_FILENAME_MAX_LEN + 20).replace(" - ", _FILENAME_SEPARATOR)
    if len(filename) <= _FILENAME_MAX_LEN:
        return filename

    short_issuer = _clip_with_ellipsis(issuer, 24)
    base = _FILENAME_SEPARATOR.join([doc_type, short_issuer, short_subject])
    filename = f"{base}{_FILENAME_SEPARATOR}{_format_euro(amount_value)}" if amount_value is not None else base
    return _clean_filename_component(filename, max_len=_FILENAME_MAX_LEN).replace(" - ", _FILENAME_SEPARATOR)


class NamingTemplateService:
    """Rendert deterministische Dateinamen aus Dokumenttyp-Templates.

    Fehlende Felder bleiben als ``{platzhalter}`` sichtbar. So ist sofort
    prüfbar, welche Information für einen konsistenten Namen noch fehlt.
    """

    def __init__(self, db: Session | None = None, *, fallback_builder: FallbackBuilder | None = None) -> None:
        self.db = db
        self.fallback_builder = fallback_builder or build_legacy_filename_from_meta

    def build_filename(self, meta: dict[str, object]) -> str:
        template = self._load_global_template(meta)
        if not template:
            return self.fallback_builder(meta)
        rendered = self.render_template(template, meta)
        filename = _clean_filename_component(rendered, max_len=_FILENAME_MAX_LEN).replace(" - ", _FILENAME_SEPARATOR)
        return filename or self.fallback_builder(meta)

    def _load_global_template(self, meta: dict[str, object]) -> str | None:
        if self.db is None:
            return None
        candidates = [
            _clean_filename_component(str(meta.get("document_type") or ""), max_len=120),
            _clean_filename_component(str(meta.get("doc_type") or ""), max_len=120),
        ]
        for doc_type in dict.fromkeys(candidate for candidate in candidates if candidate):
            template = self.db.execute(
                select(DocumentType.naming_template).where(func.lower(DocumentType.name) == doc_type.lower()).limit(1)
            ).scalar_one_or_none()
            template = str(template or "").strip()
            if template:
                return template
        return None

    def render_template(self, template: str, meta: dict[str, object]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            fmt = match.group(2)
            value = self._value_for_placeholder(key, meta)
            if value is None or value == "":
                return match.group(0)
            return self._format_value(value, fmt)

        return _PLACEHOLDER_RE.sub(replace, str(template or ""))

    def _value_for_placeholder(self, key: str, meta: dict[str, object]) -> object:
        key = str(key or "").strip()
        aliases = {
            "typ": "doc_type",
            "dokumenttyp": "doc_type",
            "korrespondent": "correspondent",
            "absender": "issuer",
            "aussteller": "issuer",
            "betreff": "subject",
            "betrag": "amount",
            "datum": "date",
            "jahr": "year",
            "monat": "month",
        }
        canonical = aliases.get(key, key)
        if canonical == "correspondent":
            correspondent = meta.get("correspondent")
            if isinstance(correspondent, dict):
                return correspondent.get("short_name") or correspondent.get("name")
            return meta.get("correspondent_short_name") or meta.get("correspondent_name") or meta.get("issuer")
        if canonical == "year":
            parsed = self._parse_date(meta.get("date"))
            return parsed.year if parsed else meta.get("year")
        if canonical == "month":
            parsed = self._parse_date(meta.get("date"))
            return parsed.month if parsed else meta.get("month")
        if canonical == "amount":
            amount = _safe_float(meta.get("amount"))
            return _format_euro(amount) if amount is not None else meta.get("amount")
        return meta.get(canonical)

    def _format_value(self, value: object, fmt: str | None) -> str:
        fmt = str(fmt or "").strip()
        if fmt == "short":
            return _clip_with_ellipsis(str(value), 40)
        if fmt in {"dd.MM.yyyy", "dd.mm.yyyy"}:
            parsed = self._parse_date(value)
            return parsed.strftime("%d.%m.%Y") if parsed else str(value)
        if fmt == "yyyy":
            parsed = self._parse_date(value)
            return str(parsed.year) if parsed else str(value)
        if fmt == "02d":
            try:
                return f"{int(value):02d}"
            except (TypeError, ValueError):
                return str(value)
        if fmt == "euro":
            amount = _safe_float(value)
            return _format_euro(amount) if amount is not None else str(value)
        return str(value)

    def _parse_date(self, value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value or "").strip()
        if not text:
            return None
        for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None

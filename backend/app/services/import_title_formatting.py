"""Seiteneffektfreie Formatierung für Import-Titel und Metadaten-Notizen."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.naming_templates import build_legacy_filename_from_meta

FILENAME_MAX_LEN = 80
FILENAME_SEPARATOR = " – "
_INVALID_TITLE_CHARS = re.compile(r'[\/\\:*?"<>|]+')
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def clean_filename_component(value: object, *, max_len: int = 80) -> str:
    normalized = _INVALID_TITLE_CHARS.sub(" ", normalize_text(value))
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip(" .,-_")
    return normalized[:max_len].rstrip(" .,-_") if len(normalized) > max_len else normalized


def sanitize_title(value: object, *, fallback: str | None = None, max_len: int = FILENAME_MAX_LEN) -> str:
    sanitized = _INVALID_TITLE_CHARS.sub(" ", str(value or ""))
    sanitized = _WHITESPACE_RE.sub(" ", sanitized).strip(" .-_")
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len].rstrip(" .-_")
    if sanitized:
        return sanitized
    if fallback:
        return sanitize_title(fallback, max_len=max_len)
    return f"Scan - {datetime.now(timezone.utc).date().isoformat()}"


def build_fallback_title(
    *,
    doc_type: str,
    sender: str | None,
    date_value: str | None,
    amount: float | None,
    currency: str | None,
) -> str:
    today = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    combinations = [
        [doc_type, sender, date_value],
        [doc_type, sender, f"{amount:.2f}{currency or ''}" if isinstance(amount, float) else None],
        [doc_type, sender],
        [doc_type, date_value],
        [f"Scan - {today}"],
    ]
    for parts in combinations:
        filtered = [sanitize_title(part) for part in parts if str(part or "").strip()]
        if filtered:
            return sanitize_title(FILENAME_SEPARATOR.join(filtered), max_len=FILENAME_MAX_LEN)
    return f"Scan - {today}"


def format_euro(amount: float) -> str:
    return f"{amount:.2f}".replace(".", ",") + "€"


def build_note_from_metadata(
    *,
    issuer: str | None,
    subject: str | None,
    doc_type: str | None,
    date_iso: str | None,
    amount: float | None,
    currency: str | None,
    max_len: int = 500,
) -> str | None:
    facts: list[str] = []
    normalized_issuer = normalize_text(issuer)
    if normalized_issuer and normalized_issuer.lower() != "unbekannt":
        facts.append(f"Absender: {normalized_issuer}")
    normalized_subject = normalize_text(subject)
    if normalized_subject:
        facts.append(f"Thema: {normalized_subject}")
    normalized_doc_type = normalize_text(doc_type)
    if normalized_doc_type and normalized_doc_type.lower() != "sonstiges":
        facts.append(f"Dokumenttyp: {normalized_doc_type}")
    normalized_date = normalize_text(date_iso)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", normalized_date):
        try:
            facts.append(f"Datum: {datetime.strptime(normalized_date, '%Y-%m-%d').strftime('%d.%m.%Y')}")
        except ValueError:
            pass
    if amount is not None and amount > 0:
        amount_text = format_euro(amount) if currency == "EUR" else f"{amount:.2f}"
        suffix = f" {currency}" if currency and currency != "EUR" else ""
        facts.append(f"Betrag: {amount_text}{suffix}")
    if not facts:
        return None
    note = " ".join(". ".join(facts).split()).strip()
    if len(note) <= max_len:
        return note
    return note[:max_len] if max_len <= 1 else f"{note[: max_len - 1].rstrip()}…"


def build_filename_from_meta(meta: dict[str, object]) -> str:
    return build_legacy_filename_from_meta(meta)

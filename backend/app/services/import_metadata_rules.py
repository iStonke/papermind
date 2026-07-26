"""Reine, regelbasierte Grundbausteine der Import-Metadatenerkennung."""

from __future__ import annotations

import re
from datetime import datetime

DATE_DMY_RE = re.compile(r"\b([0-3]?\d)[.\-/]([01]?\d)[.\-/]((?:19|20)\d{2})\b")
DATE_YMD_RE = re.compile(r"\b((?:19|20)\d{2})[.\-/]([01]?\d)[.\-/]([0-3]?\d)\b")
AMOUNT_RE = re.compile(r"\b\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})\s?(?:€|EUR)?\b", re.IGNORECASE)
DOC_TYPE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Rechnung", ("rechnung", "invoice", "rechnungsnummer", "gesamtbetrag")),
    ("Quittung", ("quittung", "kassenbon", "bon", "beleg")),
    ("Kündigung", ("kündigung", "kuendigung", "ordentliche kündigung")),
    ("Vertrag", ("vertrag", "vereinbarung", "contract")),
    ("Mahnung", ("mahnung", "zahlungserinnerung", "überfällig", "ueberfaellig")),
    ("Bescheid", ("bescheid", "amt", "behörde", "behoerde")),
    ("Protokoll", ("protokoll", "sitzung", "meeting")),
    ("Brief", ("sehr geehrte", "mit freundlichen grüßen", "mit freundlichen gruessen")),
]
DOC_TYPES_ALLOWED = frozenset({
    "Rechnung", "Quittung", "Mahnung", "Vertrag", "Kündigung", "Brief", "Bescheid", "Protokoll", "Sonstiges",
})
_DATE_CONTEXT_RE = re.compile(
    r"(?:datum|rechnungsdatum|briefdatum|belegdatum|leistungsdatum|"
    r"ausgestellt\s*am|erstellt\s*am|bescheid\s*vom|bescheid\s*für|"
    r"gültig\s*ab|fakturadatum)\s*:?\s*"
    r"([0-3]?\d)[.\-/]([01]?\d)[.\-/]((?:19|20)\d{2})",
    re.IGNORECASE,
)


def detect_document_type(text_value: str) -> str:
    normalized = str(text_value or "").lower()
    if any(token in normalized for token in ("rechnung", "invoice", "rechnungsnr", "rechnungsnummer", "rg ")):
        return "Rechnung"
    for doc_type, keywords in DOC_TYPE_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return doc_type
    return "Sonstiges"


def detect_document_type_improved(text_value: str) -> str:
    """Wortgrenzen vermeiden etwa den Fehlalarm von „Abrechnung“ als Rechnung."""
    lower = str(text_value or "").lower()
    if re.search(
        r"\b(bescheid|finanzamt|steuerbescheid|einkommensteuer(?:bescheid)?|lohnsteuer(?:bescheid)?|umsatzsteuer(?:bescheid)?"
        r"|grundsteuer(?:bescheid)?|gewerbesteuer(?:bescheid)?|rentenbescheid|bewilligungsbescheid"
        r"|widerspruchsbescheid|ablehnungsbescheid|anerkennungsbescheid)\b",
        lower,
    ):
        return "Bescheid"
    if re.search(r"\brechnung\b|\binvoice\b|\brechnungsnr\b|\brechnungsnummer\b", lower):
        return "Rechnung"
    for doc_type, keywords in DOC_TYPE_KEYWORDS:
        if doc_type not in {"Rechnung", "Bescheid"} and any(keyword in lower for keyword in keywords):
            return doc_type
    return "Sonstiges"


def normalize_document_type(value: str | None, allowed_doc_types: list[str] | None = None) -> str | None:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        return None
    allowed = [str(item).strip() for item in (allowed_doc_types or []) if str(item).strip()]
    if allowed:
        exact = {item.lower(): item for item in allowed}.get(normalized.lower())
        if exact:
            return exact
    elif normalized in DOC_TYPES_ALLOWED:
        return normalized
    lower = normalized.lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS:
        if doc_type.lower() in lower or any(keyword in lower for keyword in keywords):
            return doc_type
    return None


def detect_amount_currency(text_value: str) -> tuple[float | None, str | None]:
    source = str(text_value or "")
    matches = list(AMOUNT_RE.finditer(source))
    if not matches:
        return None, None
    prioritized = None
    for match in matches:
        window = source[max(0, match.start() - 28) : min(len(source), match.end() + 28)].lower()
        if any(key in window for key in ("gesamt", "summe", "total", "endbetrag", "brutto")):
            prioritized = match
    token = (prioritized or matches[-1]).group(0).replace(" ", "")
    currency = "EUR" if ("€" in token or "eur" in token.lower()) else None
    numeric = re.sub(r"[^0-9,.-]", "", token).replace(".", "").replace(",", ".")
    try:
        amount = round(float(numeric), 2)
    except ValueError:
        return None, currency
    return (amount, currency) if amount > 0 else (None, None)


def extract_document_date(text_value: str) -> str | None:
    """Liefert das plausibelste Datum als ISO-String, bevorzugt Kontexttreffer."""
    text = str(text_value or "")
    match = _DATE_CONTEXT_RE.search(text)
    if match:
        try:
            return datetime(int(match.group(3)), int(match.group(2)), int(match.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    for match in DATE_DMY_RE.finditer(text):
        try:
            date_value = datetime(int(match.group(3)), int(match.group(2)), int(match.group(1)))
            if 2000 <= date_value.year <= 2099:
                return date_value.strftime("%Y-%m-%d")
        except ValueError:
            pass
    for match in DATE_YMD_RE.finditer(text):
        try:
            date_value = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if 2000 <= date_value.year <= 2099:
                return date_value.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None

"""Quality gates shared by import extraction and cached model responses."""
from __future__ import annotations

import re
from datetime import date

_EMPTY_VALUES = frozenset({"", "ohne betreff", "kein betreff", "unbekannt", "unknown", "null", "none", "n/a", "nicht erkannt", "unbenannt", "untitled", "sonstiges"})


def meaningful_value(value: object) -> str | None:
    text = " ".join(str(value or "").split()).strip(" .–-_")
    return None if text.casefold() in _EMPTY_VALUES else text or None


def text_quality(value: str) -> float:
    """Prefer readable words over longer OCR garbage; retain original layout."""
    words = re.findall(r"[^\W\d_]{2,}", value, flags=re.UNICODE)
    letters = sum(char.isalpha() for char in value)
    visible = sum(not char.isspace() for char in value)
    noise = sum(char in "�|{}[]\\" for char in value)
    return min(len(words), 300) * 3 + letters / max(visible, 1) * 30 - noise * 4


def evidence_for(value: object, text: str) -> dict[str, object] | None:
    needle = meaningful_value(value)
    if not needle:
        return None
    for index, line in enumerate(text.splitlines()):
        if needle.casefold() in line.casefold() or re.fullmatch(r"\d{4}-\d{2}-\d{2}", needle) and date_supported(needle, line):
            return {"text": line.strip()[:240], "line": index + 1}
    return None


def date_supported(iso: str, text: str) -> bool:
    try:
        value = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return False
    if iso in text:
        return True
    numeric = rf"(?<!\d)0?{value.day}\s*[.\-/]\s*0?{value.month}\s*[.\-/]\s*{value.year}(?!\d)"
    months = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
    named = rf"(?<!\d)0?{value.day}\.?\s+{months[value.month - 1]}\s+{value.year}(?!\d)"
    return bool(re.search(numeric, text) or re.search(named, text, re.IGNORECASE))


def grounded_summary(summary: object, text: str) -> str | None:
    candidate = " ".join(str(summary or "").split()).strip()
    if not meaningful_value(candidate):
        return None
    context_digits = re.sub(r"[^\d]", "", text)
    # Numbers, reference IDs and dates are especially costly hallucinations.
    # Reject a summary with a numeric fact absent from the document; the caller
    # can still build a deterministic note from supported metadata.
    for token in re.findall(r"\d[\d.,/\-]*\d|\d", candidate):
        digits = re.sub(r"\D", "", token)
        if digits and digits not in context_digits:
            return None
    if re.search(r"\b(?:frist|fällig|faellig|zahlbar|muss|verpflichtet)\b", candidate, re.IGNORECASE) and not re.search(r"\b(?:frist|fällig|faellig|zahlbar|muss|verpflichtet)\b", text, re.IGNORECASE):
        return None
    return candidate[:240]


def amount_supported(amount: float, text: str) -> bool:
    for line in text.splitlines():
        if not re.search(r"€|\b(?:EUR|Betrag|Summe|Gesamt|Total|Preis)\b", line, re.IGNORECASE):
            continue
        for token in re.findall(r"\d+(?:[.,]\d+)*", line):
            number = token
            if ',' in number:
                number = number.replace('.', '').replace(',', '.')
            elif number.count('.') > 1 or '.' in number and len(number.rsplit('.', 1)[1]) == 3:
                number = number.replace('.', '')
            try:
                if round(float(number), 2) == amount:
                    return True
            except ValueError:
                continue
    return False

"""Tolerante, reine Parser für Antworten lokaler Metadaten-Modelle."""

from __future__ import annotations

import json
import re

_WHITESPACE_RE = re.compile(r"\s+")
LOOSE_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "doc_type": re.compile(r"\b(?:doc_type|doctype|typ|dokumenttyp)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "issuer": re.compile(r"\b(?:issuer|absender|firma|company)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "subject": re.compile(r"\b(?:subject|betreff|thema)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "amount": re.compile(r"\b(?:amount|betrag|summe|gesamtbetrag)\b\s*[:=]\s*(.+)", re.IGNORECASE),
    "currency": re.compile(r"\b(?:currency|währung|waehrung)\b\s*[:=]\s*(.+)", re.IGNORECASE),
}


def normalize_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def coerce_llm_scalar(value: object) -> str | None:
    """Entpackt übliche Modell-Container wie ``{"text": "…"}`` rekursiv."""
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("text", "value", "name", "label"):
            nested = coerce_llm_scalar(value.get(key))
            if nested:
                return nested
        return None
    if isinstance(value, list):
        for item in value:
            nested = coerce_llm_scalar(item)
            if nested:
                return nested
        return None
    return normalize_text(value) or None


def extract_json_object(value: object) -> dict[str, object] | None:
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
    return parsed if isinstance(parsed, dict) else None


def extract_loose_fields(raw_text: object) -> dict[str, object] | None:
    lines = [normalize_text(line) for line in str(raw_text or "").splitlines()]
    extracted: dict[str, object] = {}
    for key, pattern in LOOSE_FIELD_PATTERNS.items():
        for line in lines:
            match = pattern.search(line)
            if match:
                extracted[key] = normalize_text(match.group(1))
                break
    return extracted or None


def safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(str(value).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return None

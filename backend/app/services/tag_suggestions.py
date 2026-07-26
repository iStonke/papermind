"""Gemeinsame Regeln für automatische Dokument-Tags.

Manuelles Tagging in der API und automatisches Tagging im Worker verwenden
denselben Normalisierungs-, Fallback- und KI-Antwortpfad. Nur die bewusst
unterschiedlichen Aufruf-Limits werden an die Funktionen übergeben.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

import httpx

logger = logging.getLogger("papermind.tag_suggestions")

BLOCKED_CANDIDATE_KEYS = {
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
    "keine schlagwörter",
    "keine schlagworte gefunden",
    "keine schlagwoerter gefunden",
    "keine schlagwörter gefunden",
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
BLOCKED_CANDIDATE_PREFIXES = (
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
BLOCKED_CANDIDATE_CONTAINS = (
    "keine information",
    "keine infos",
    "keine relevanten information",
    "nicht gefunden",
    "finde ich keine",
    "finde keine",
)
STOPWORDS = {
    "aber", "alle", "alles", "als", "also", "am", "an", "auch", "auf", "aus", "bei", "bin", "bis",
    "das", "dass", "dein", "dem", "den", "der", "des", "die", "dies", "diese", "dieser", "doch", "dort",
    "ein", "eine", "einem", "einer", "eines", "er", "es", "etwas", "für", "hat", "haben", "hier", "ich",
    "ihm", "im", "in", "ist", "jede", "jeder", "kann", "kein", "keine", "mit", "nach", "nicht", "noch",
    "nur", "oder", "sein", "seine", "sich", "sie", "sind", "so", "und", "uns", "vom", "von", "vor", "war",
    "was", "weil", "wenn", "wer", "wie", "wir", "wird", "zu", "zum", "zur",
}


def normalize_tag_name(raw_value: str) -> str:
    cleaned = re.sub(r"[^A-Za-zÄÖÜäöüß0-9\-/ ]+", " ", str(raw_value or ""))
    normalized = " ".join(cleaned.split()).strip()
    return normalized[:48].rstrip() if normalized else ""


def normalize_tag_key(raw_value: str) -> str:
    normalized = normalize_tag_name(raw_value).lower()
    return re.sub(r"[^a-z0-9äöüß]+", " ", normalized).strip()


def is_blocked_tag_candidate(candidate: str) -> bool:
    candidate_key = normalize_tag_key(candidate)
    if not candidate_key:
        return True
    if candidate_key in BLOCKED_CANDIDATE_KEYS:
        return True
    if any(candidate_key.startswith(prefix) for prefix in BLOCKED_CANDIDATE_PREFIXES):
        return True
    return any(fragment in candidate_key for fragment in BLOCKED_CANDIDATE_CONTAINS)


def fallback_tag_candidates(text_value: str, *, max_tags: int) -> list[str]:
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-]{2,}", text_value.lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS and not token.isnumeric())
    candidates: list[str] = []
    seen: set[str] = set()
    for token, _ in counts.most_common(max_tags * 4):
        normalized = normalize_tag_name(token)
        if not normalized or is_blocked_tag_candidate(normalized):
            continue
        label = normalized[0].upper() + normalized[1:]
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(label)
        if len(candidates) >= max_tags:
            break
    return candidates


def parse_tag_candidates(raw_answer: str, *, max_tags: int) -> tuple[list[str], bool]:
    raw_answer = str(raw_answer or "").strip()
    if not raw_answer:
        return [], False
    array_match = re.search(r"\[[\s\S]*\]", raw_answer)
    candidate_text = array_match.group(0) if array_match else raw_answer
    try:
        parsed = json.loads(candidate_text)
        raw_candidates = [str(item) for item in parsed] if isinstance(parsed, list) else []
    except Exception:  # noqa: BLE001 - KI-Antwort darf auch eine einfache Liste sein
        raw_candidates = [part.strip(" -\t\r\n\"'") for part in re.split(r"[,;\n]", raw_answer) if part.strip()]
        # Ein einzelner kurzer Bare-Tag ("Rechnung") bleibt zulässig. Längerer
        # Freitext ist dagegen sehr wahrscheinlich eine Erklärung der KI und
        # soll den lokalen Fallback auslösen statt als Tag gespeichert zu werden.
        if len(raw_candidates) == 1 and len(normalize_tag_name(raw_candidates[0]).split()) > 3:
            raw_candidates = []

    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = normalize_tag_name(candidate)
        if not normalized or is_blocked_tag_candidate(normalized):
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized_candidates.append(normalized)
        if len(normalized_candidates) >= max_tags:
            break
    return normalized_candidates, bool(raw_candidates)


def suggest_tags_with_ai(
    text_value: str,
    *,
    max_tags: int,
    max_text_chars: int,
    ai_base_url: str,
    timeout_seconds: float,
) -> list[str]:
    normalized_text = " ".join(str(text_value or "").split()).strip()
    if not normalized_text:
        return []
    payload = {
        "model": "default",
        "system_prompt": (
            "Du extrahierst kurze deutsche Schlagwörter für Dokumente. "
            f"Antworte ausschließlich mit einem JSON-Array mit maximal {max_tags} Strings."
        ),
        "max_sentences": 1,
        "max_tokens": 120,
        "temperature": 0.1,
        "question": f"Extrahiere bis zu {max_tags} prägnante Tags.",
        "user_prompt": (
            "Gib nur ein JSON-Array zurück, z.B. [\"Rechnung\", \"KFZ\"]. Keine Erklärungen.\n\n"
            f"TEXT:\n{normalized_text[:max_text_chars]}"
        ),
        "contexts": [],
    }
    try:
        response = httpx.post(
            f"{ai_base_url.rstrip('/')}/chat",
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        raw_answer = str(response.json().get("answer") or "")
    except Exception as exc:  # noqa: BLE001 - KI ist optional, Fallback bleibt lokal
        logger.warning("auto-tag AI call failed: %s", exc)
        return fallback_tag_candidates(normalized_text, max_tags=max_tags)

    candidates, had_explicit_answer = parse_tag_candidates(raw_answer, max_tags=max_tags)
    if candidates:
        return candidates
    return [] if had_explicit_answer else fallback_tag_candidates(normalized_text, max_tags=max_tags)

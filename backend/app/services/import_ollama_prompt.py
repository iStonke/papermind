"""Seiteneffektfreie Auswahl und Aufbereitung des OCR-Kontexts für Ollama."""

from __future__ import annotations

import re

from app.services.import_metadata_rules import AMOUNT_RE, DATE_DMY_RE, DATE_YMD_RE

_SIGNAL_KEYWORDS = (
    "rechnung", "rechnungsnummer", "rechnungsnr", "invoice", "gesamtbetrag", "summe", "total", "betrag", "datum",
    "rechnungsdatum", "belegdatum", "kundennummer", "kunden-nr", "vertragsnummer", "aktenzeichen", "frist", "fällig",
    "faellig", "bescheid", "steuer", "versicherung", "kündigung", "kuendigung", "vertrag", "mahnung", "zahlbar",
)


def build_naming_examples_block(examples: list[str] | None, *, max_examples: int = 3, max_len: int = 80) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in examples or []:
        name = " ".join(str(raw or "").split()).strip()
        if name.lower().endswith(".pdf"):
            name = name[:-4].rstrip()
        if not name:
            continue
        name = name[:max_len].rstrip() if len(name) > max_len else name
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        cleaned.append(name)
        if len(cleaned) >= max_examples:
            break
    if not cleaned:
        return ""
    return (
        "BEISPIELE für bereits vergebene Dateinamen ähnlicher Dokumente. "
        "Orientiere dich für \"subject\" am Schreibmuster/Stil dieser Beispiele, "
        "übernimm sie aber NICHT wörtlich:\n"
        + "\n".join(f"- {name}" for name in cleaned)
        + "\n\n"
    )


def select_staging_llm_text(ocr_text: str, max_chars: int) -> str:
    limit = max(300, int(max_chars or 800))
    raw = str(ocr_text or "").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in raw.split("\n")]
    lines = [line for line in lines if line]
    if len(lines) <= 2:
        compact = " ".join(raw.split())
        if len(compact) <= limit:
            return compact
        lines = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+|(?<=€)\s+|(?<=EUR)\s+", compact, flags=re.IGNORECASE) if chunk.strip()]
        if len(lines) <= 1:
            lines = [compact[index : index + 180].strip() for index in range(0, len(compact), 180)]
    if len("\n".join(lines)) <= limit:
        return "\n".join(lines)[:limit].rstrip()
    selected = {index: line for index, line in enumerate(lines[:18])}
    selected.update({index: line for index, line in enumerate(lines[-8:], start=max(0, len(lines) - 8))})
    scored: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        score = 80 if any(keyword in lowered for keyword in _SIGNAL_KEYWORDS) else 0
        score += 45 if AMOUNT_RE.search(line) else 0
        score += 35 if DATE_DMY_RE.search(line) or DATE_YMD_RE.search(line) else 0
        score += 20 if re.search(r"\b[A-Z0-9][A-Z0-9-]{4,}\b", line) else 0
        score -= 20 if len(line) > 180 else 0
        if score > 0:
            scored.append((score, index, line))
    for _score, index, line in sorted(scored, key=lambda item: (-item[0], item[1]))[:32]:
        selected[index] = line
    deduped: list[str] = []
    seen: set[str] = set()
    for index in sorted(selected):
        line = selected[index]
        if line.casefold() not in seen:
            seen.add(line.casefold())
            deduped.append(line)
    result: list[str] = []
    current_len = 0
    for line in deduped:
        projected = current_len + len(line) + (1 if result else 0)
        if projected > limit:
            remaining = limit - current_len - (1 if result else 0)
            if remaining > 40:
                result.append(line[:remaining].rstrip())
            break
        result.append(line)
        current_len = projected
    return "\n".join(result).strip()

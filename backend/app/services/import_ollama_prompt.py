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
    scored = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        score = 80 if any(keyword in lowered for keyword in _SIGNAL_KEYWORDS) else 0
        score += 45 if AMOUNT_RE.search(line) else 0
        score += 35 if DATE_DMY_RE.search(line) or DATE_YMD_RE.search(line) else 0
        score += 100 if re.match(r"(?:betreff|thema)\s*:", lowered) else 0
        score += 70 if index + 1 < len(lines) and re.match(r"(?:Sehr geehrt|Guten Tag)", lines[index + 1], re.IGNORECASE) else 0
        if score:
            scored.append((score, index))
    selected = {}
    seen = set()
    remaining = limit
    # Keep a small sender/header context, then reserve the bulk for facts.
    ranked = list(range(min(3, len(lines)))) + [index for _, index in sorted(scored, key=lambda item: (-item[0], item[1]))] + list(range(3, len(lines)))
    for index in ranked:
        line = lines[index]
        if line.casefold() in seen:
            continue
        allocation = min(len(line), 120 if index < 3 else 240, remaining - 1)
        if allocation < 20:
            continue
        selected[index] = line[:allocation]
        seen.add(line.casefold())
        remaining -= allocation + 1
    return "\n".join(selected[index] for index in sorted(selected)).strip()

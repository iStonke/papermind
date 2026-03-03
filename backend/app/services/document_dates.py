import re
from dataclasses import dataclass
from datetime import date
from typing import Any


_DATE_PATTERN = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_DATE_PATTERN_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")

_INVOICE_CONTEXT_KEYWORDS = (
    "rechnung",
    "invoice",
    "brief",
    "anschrift",
    "kundennummer",
    "kunden-nr",
    "steuer",
    "ust-id",
)

_VEHICLE_MARKERS = ("erstzulassung", "nächste hu", "naechste hu", "hauptuntersuchung")
_DUE_MARKERS = ("zahlbar bis", "fällig", "faellig", "fälligkeit", "faelligkeit")
_SERVICE_MARKERS = ("leistungsdatum",)


@dataclass
class DocumentDateExtractionResult:
    best_date: date | None
    best_confidence: float | None
    candidates: list[dict[str, Any]]


def _normalize_line(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _parse_date_parts(day: int, month: int, year: int) -> date | None:
    if year < 100:
        year = 2000 + year if year < 70 else 1900 + year
    if year < 1900 or year > 2100:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_date_match(match: re.Match[str]) -> date | None:
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    return _parse_date_parts(day=day, month=month, year=year)


def _parse_date_match_iso(match: re.Match[str]) -> date | None:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return _parse_date_parts(day=day, month=month, year=year)


def _classify_line(line: str, *, invoice_context: bool) -> tuple[str, str | None, float, int, bool]:
    normalized = _normalize_line(line).lower()
    if not normalized:
        return "unknown", None, 0.0, 0, False

    if any(marker in normalized for marker in _VEHICLE_MARKERS):
        return "vehicle", "KFZ-Datum", 0.2, 5, False
    if any(marker in normalized for marker in _DUE_MARKERS):
        return "due_date", "Fällig/Zahlbar bis", 0.45, 15, False
    if any(marker in normalized for marker in _SERVICE_MARKERS):
        return "service_date", "Leistungsdatum", 0.5, 20, False
    if "rechnungsdatum" in normalized:
        return "document_date", "Rechnungsdatum", 0.9, 100, True
    if "belegdatum" in normalized:
        return "document_date", "Belegdatum", 0.82, 90, True
    if re.search(r"\bdatum\b", normalized):
        if invoice_context:
            return "document_date", "Datum", 0.78, 80, True
        return "unknown", "Datum", 0.58, 30, True
    return "unlabeled", None, 0.6, 40, True


def extract_document_date_candidates(page_texts: list[tuple[int, str]]) -> DocumentDateExtractionResult:
    all_text = "\n".join(_normalize_line(text) for _, text in page_texts).lower()
    invoice_context = any(keyword in all_text for keyword in _INVOICE_CONTEXT_KEYWORDS)

    candidates: list[dict[str, Any]] = []
    best_value: date | None = None
    best_confidence: float | None = None
    best_score = float("-inf")

    for page_number, raw_text in page_texts:
        lines = str(raw_text or "").splitlines()
        for line in lines:
            kind, label, confidence, priority, eligible_for_best = _classify_line(line, invoice_context=invoice_context)
            if not line.strip():
                continue

            parsed_dates: list[date] = []
            for match in _DATE_PATTERN.finditer(line):
                parsed = _parse_date_match(match)
                if parsed is not None:
                    parsed_dates.append(parsed)
            for match in _DATE_PATTERN_ISO.finditer(line):
                parsed = _parse_date_match_iso(match)
                if parsed is not None:
                    parsed_dates.append(parsed)

            for parsed_date in parsed_dates:
                candidate = {
                    "value": parsed_date.isoformat(),
                    "label": label,
                    "kind": kind,
                    "page": int(page_number) if page_number else None,
                    "confidence": round(confidence, 3),
                }
                candidates.append(candidate)

                if not eligible_for_best:
                    continue
                if kind not in {"document_date", "unlabeled"}:
                    continue

                score = priority + confidence
                if score > best_score:
                    best_score = score
                    best_value = parsed_date
                    best_confidence = confidence

    candidates.sort(key=lambda item: ((item.get("page") or 0), item.get("value") or "", item.get("kind") or ""))
    return DocumentDateExtractionResult(best_date=best_value, best_confidence=best_confidence, candidates=candidates)


def apply_ocr_document_date_result(
    document: Any,
    extraction_result: DocumentDateExtractionResult,
    *,
    overwrite_manual: bool = False,
) -> bool:
    candidates = extraction_result.candidates or None
    document.document_date_candidates = candidates

    if extraction_result.best_date is None:
        return False

    if (
        not overwrite_manual
        and (document.document_date_source or "manual") == "manual"
        and document.document_date is not None
    ):
        return False

    document.document_date = extraction_result.best_date
    document.document_date_source = "ocr"
    document.document_date_confidence = extraction_result.best_confidence
    return True

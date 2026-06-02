import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

logger = logging.getLogger("papermind.ollama_classification")

DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT_SECONDS = 60.0

CLASSIFICATION_KEYS = {
    "document_type",
    "document_date",
    "sender",
    "recipient",
    "amount",
    "currency",
    "summary",
    "tags",
    "confidence",
}


class OllamaClassificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaClassificationInput:
    document_id: str
    ocr_text: str
    confidence_score: float | None = None
    quality_status: str | None = None


@dataclass(frozen=True)
class OllamaClassificationResult:
    document_type: str | None
    document_date: date | None
    sender: str | None
    recipient: str | None
    amount: Decimal | None
    currency: str | None
    summary: str | None
    tags: list[str] | None
    confidence: float | None
    raw_response: str


def _normalize_text(value: Any, *, max_length: int | None = None) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        return None
    if max_length is not None and len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip()
    return normalized


def _parse_date(value: Any) -> date | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    normalized = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed.quantize(Decimal("0.01"))


def _parse_confidence(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return round(parsed, 3)


def _parse_tags(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    tags: list[str] = []
    seen = set()
    for item in value:
        normalized = _normalize_text(item, max_length=48)
        if normalized is None:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(normalized)
        if len(tags) >= 5:
            break
    return tags or None


def _extract_json_object(raw_value: str) -> dict[str, Any]:
    raw = str(raw_value or "").strip()
    if not raw:
        raise OllamaClassificationError("Ollama returned an empty response")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise OllamaClassificationError("Ollama response did not contain a JSON object")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise OllamaClassificationError(f"Ollama JSON parsing failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise OllamaClassificationError("Ollama JSON response is not an object")
    return parsed


def parse_ollama_classification_response(raw_value: str) -> OllamaClassificationResult:
    parsed = _extract_json_object(raw_value)
    missing_keys = sorted(CLASSIFICATION_KEYS - set(parsed.keys()))
    if missing_keys:
        raise OllamaClassificationError(f"Ollama JSON response is missing keys: {', '.join(missing_keys)}")

    return OllamaClassificationResult(
        document_type=_normalize_text(parsed.get("document_type"), max_length=64),
        document_date=_parse_date(parsed.get("document_date")),
        sender=_normalize_text(parsed.get("sender"), max_length=255),
        recipient=_normalize_text(parsed.get("recipient"), max_length=255),
        amount=_parse_decimal(parsed.get("amount")),
        currency=_normalize_text(parsed.get("currency"), max_length=8),
        summary=_normalize_text(parsed.get("summary"), max_length=2000),
        tags=_parse_tags(parsed.get("tags")),
        confidence=_parse_confidence(parsed.get("confidence")),
        raw_response=raw_value,
    )


def build_ollama_classification_payload(
    payload: OllamaClassificationInput,
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
    allowed_document_types: list[str] | None = None,
) -> dict[str, Any]:
    normalized_text = " ".join(str(payload.ocr_text or "").split()).strip()
    doc_type_names = [str(name).strip() for name in (allowed_document_types or []) if str(name).strip()]
    doc_type_hint = "|".join(doc_type_names[:120]) if doc_type_names else "Rechnung|Vertrag|Brief|Kontoauszug|Sonstiges"
    schema = {
        "document_type": f"{doc_type_hint} oder null",
        "document_date": "YYYY-MM-DD oder null",
        "sender": "Absender/Aussteller als String oder null",
        "recipient": "Empfänger als String oder null",
        "amount": "Zahl ohne Währung oder null",
        "currency": "ISO-Währungscode, z.B. EUR, oder null",
        "summary": "1-2 deutsche Sätze oder null",
        "tags": "Array mit 2-5 deutschen Tags oder []",
        "confidence": "Zahl zwischen 0.0 und 1.0",
    }
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "prompt": (
            "Du klassifizierst OCR-Text aus Dokumenten. Antworte ausschließlich auf Deutsch und ausschließlich als "
            "gültiges JSON-Objekt. Kein Markdown, keine Erklärungen, kein zusätzlicher Text.\n"
            "Lasse keine Schlüssel weg. Wenn ein Feld nicht sicher erkennbar ist, setze es auf null. "
            "Bei Tags nutze eine leere Liste, falls keine sinnvollen Tags erkennbar sind. "
            "Beträge nur bei Rechnungen extrahieren; sonst amount und currency null.\n\n"
            "JSON-SCHEMA:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            f"DOCUMENT_ID: {payload.document_id}\n"
            f"OCR_CONFIDENCE: {payload.confidence_score}\n"
            f"OCR_QUALITY: {payload.quality_status}\n\n"
            f"OCR_TEXT:\n{normalized_text[:12000]}"
        ),
    }


class OllamaClassificationService:
    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
        allowed_document_types: list[str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.allowed_document_types = allowed_document_types

    def build_payload(self, payload: OllamaClassificationInput) -> dict[str, Any]:
        return build_ollama_classification_payload(
            payload,
            model=self.model,
            allowed_document_types=self.allowed_document_types,
        )

    def classify(self, payload: OllamaClassificationInput) -> OllamaClassificationResult:
        request_payload = self.build_payload(payload)
        url = f"{self.base_url}/api/generate"
        logger.info(
            "ollama classification request document_id=%s url=%s model=%s text_chars=%s",
            payload.document_id,
            url,
            self.model,
            len(payload.ocr_text or ""),
        )
        try:
            response = httpx.post(url, json=request_payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            response_payload = response.json()
        except Exception as exc:
            raise OllamaClassificationError(f"Ollama request failed: {exc}") from exc

        raw_response = str(response_payload.get("response") or "").strip()
        logger.info(
            "ollama classification response document_id=%s response_chars=%s",
            payload.document_id,
            len(raw_response),
        )
        logger.debug("ollama classification raw document_id=%s response=%s", payload.document_id, raw_response[:4000])
        return parse_ollama_classification_response(raw_response)

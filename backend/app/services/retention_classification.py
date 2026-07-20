"""Narrow Ollama classifier for the German paper-retention question.

Mirrors the JSON-mode request/parse shape of ``ollama_classification.py`` but
asks a single focused question: must the paper original be kept, or is a scan
sufficient, and for how long. Used on-demand by
``DocumentRetentionService.suggest_retention``.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("papermind.retention_classification")

DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_TIMEOUT_SECONDS = 60.0
# Modell zwischen den Calls im Speicher halten – siehe ollama_classification.py.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m").strip() or "30m"

_PAPER_ORIGINAL_VALUES = {"unclear", "keep", "scan_sufficient", "not_applicable"}


class OllamaRetentionError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaRetentionRule:
    paper_original: str
    period_years: int | None
    basis: str


@dataclass(frozen=True)
class OllamaRetentionInput:
    document_id: str
    ocr_text: str
    document_type: str | None = None
    tags: tuple[str, ...] = ()
    usage_mode: str = "business"
    rule: OllamaRetentionRule | None = None


@dataclass(frozen=True)
class OllamaRetentionResult:
    paper_original: str
    period_years: int | None
    reason: str | None
    raw_response: str


def _extract_json_object(raw_value: str) -> dict[str, Any]:
    raw = str(raw_value or "").strip()
    if not raw:
        raise OllamaRetentionError("Ollama returned an empty response")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise OllamaRetentionError("Ollama response did not contain a JSON object")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise OllamaRetentionError(f"Ollama JSON parsing failed: {exc}") from exc
    if not isinstance(parsed, dict):
        raise OllamaRetentionError("Ollama JSON response is not an object")
    return parsed


def _parse_paper_original(value: Any) -> str:
    normalized = " ".join(str(value or "").split()).strip().lower()
    return normalized if normalized in _PAPER_ORIGINAL_VALUES else "unclear"


def _parse_period_years(value: Any) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in ("", "null", "unklar", "unknown", "none"):
        return None
    if normalized in ("unbegrenzt", "dauerhaft", "-1"):
        return -1
    try:
        parsed = int(float(normalized))
    except (TypeError, ValueError):
        return None
    if parsed < -1:
        return None
    return min(parsed, 100)


def _normalize_reason(value: Any) -> str | None:
    normalized = " ".join(str(value or "").split()).strip()
    return normalized[:500] or None


def parse_ollama_retention_response(raw_value: str) -> OllamaRetentionResult:
    parsed = _extract_json_object(raw_value)
    return OllamaRetentionResult(
        paper_original=_parse_paper_original(parsed.get("paper_original")),
        period_years=_parse_period_years(parsed.get("period_years")),
        reason=_normalize_reason(parsed.get("reason")),
        raw_response=raw_value,
    )


def build_ollama_retention_payload(
    payload: OllamaRetentionInput,
    *,
    model: str = DEFAULT_OLLAMA_MODEL,
) -> dict[str, Any]:
    normalized_text = " ".join(str(payload.ocr_text or "").split()).strip()
    schema = {
        "paper_original": "eines von: keep, scan_sufficient, not_applicable, unclear",
        "period_years": "Ganzzahl (Jahre ab Dokumentdatum), -1 fuer unbegrenzt, oder null falls unklar",
        "reason": "1 knapper deutscher Satz, moeglichst mit Rechtsgrundlage",
    }
    usage_label = "privat (kein Gewerbe)" if payload.usage_mode == "private" else "geschäftlich / gewerblich"
    context_lines = [
        f"DOCUMENT_ID: {payload.document_id}",
        f"NUTZUNG: {usage_label}",
    ]
    if payload.document_type:
        context_lines.append(f"DOKUMENTTYP: {payload.document_type}")
    normalized_tags = [tag for tag in (t.strip() for t in payload.tags) if tag]
    if normalized_tags:
        context_lines.append(f"TAGS: {', '.join(normalized_tags[:20])}")
    if payload.rule is not None:
        period = payload.rule.period_years
        if period is None:
            period_text = "unklar"
        elif period == -1:
            period_text = "unbegrenzt"
        else:
            period_text = f"{period} Jahre"
        rule_parts = [f"Papieroriginal={payload.rule.paper_original}", f"Frist={period_text}"]
        if payload.rule.basis:
            rule_parts.append(f"Grundlage={payload.rule.basis}")
        context_lines.append("HAUSREGEL (kuratierter Standard für diesen Dokumenttyp): " + ", ".join(rule_parts))

    return {
        "model": model,
        "stream": False,
        "format": "json",
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "prompt": (
            "Du bewertest fuer ein deutsches Dokumentenarchiv, ob das Papieroriginal eines Dokuments "
            "aufbewahrt werden muss oder ein Scan ausreicht, und wie lange es aufbewahrt werden muss. "
            "Beziehe dich auf deutsches Recht (u.a. § 147 AO, § 257 HGB, § 14b UStG, Verjährungsfristen "
            "nach BGB). Nutze 'keep' nur, wenn ein unterschriebenes/beglaubigtes Original oder eine Urkunde "
            "nötig ist (z.B. Verträge mit Unterschrift, Zeugnisse, notarielle Urkunden, Bürgschaften). "
            "Nutze 'scan_sufficient', wenn eine ordnungsgemäße digitale Aufbewahrung rechtlich ausreicht "
            "(z.B. Rechnungen, Kontoauszüge, Standardkorrespondenz). Nutze 'not_applicable', wenn keine "
            "Aufbewahrungspflicht besteht (z.B. Werbung, informelle Mitteilungen). Nutze 'unclear', wenn "
            "sich das aus dem Text nicht sicher beurteilen lässt.\n"
            "Nutze DOKUMENTTYP und TAGS (falls angegeben) als zusätzliche Einordnungshilfe für Art des "
            "Dokuments und Aufbewahrungsfrist; der OCR_TEXT bleibt maßgeblich, wenn er den Metadaten "
            "widerspricht.\n"
            "Ist eine HAUSREGEL angegeben, übernimm sie als Standard (paper_original, period_years und "
            "Grundlage im reason), sofern der OCR_TEXT ihr nicht klar widerspricht.\n"
            "Beachte NUTZUNG: Bei 'privat' bestehen für Privatpersonen meist KEINE gesetzlichen "
            "Aufbewahrungspflichten (Ausnahmen z.B. § 14b UStG bei Bauleistungen); bei 'geschäftlich' "
            "gelten die Fristen aus § 147 AO und § 257 HGB.\n"
            "Antworte ausschließlich auf Deutsch und ausschließlich als gültiges JSON-Objekt ohne "
            "Markdown oder Zusatztext.\n\n"
            "JSON-SCHEMA:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            + "\n".join(context_lines)
            + "\n\n"
            f"OCR_TEXT:\n{normalized_text[:8000]}"
        ),
    }


class OllamaRetentionService:
    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def classify(self, payload: OllamaRetentionInput) -> OllamaRetentionResult:
        request_payload = build_ollama_retention_payload(payload, model=self.model)
        url = f"{self.base_url}/api/generate"
        logger.info(
            "ollama retention request document_id=%s url=%s model=%s text_chars=%s",
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
            raise OllamaRetentionError(f"Ollama request failed: {exc}") from exc

        raw_response = str(response_payload.get("response") or "").strip()
        logger.info(
            "ollama retention response document_id=%s response_chars=%s",
            payload.document_id,
            len(raw_response),
        )
        logger.debug("ollama retention raw document_id=%s response=%s", payload.document_id, raw_response[:2000])
        return parse_ollama_retention_response(raw_response)

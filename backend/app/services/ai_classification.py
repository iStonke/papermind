"""Shared Ollama classification logic.

Runs the Ollama document classification and persists the ``ai_*`` fields on a
:class:`~app.models.document.Document`. Used by the OCR worker (during the OCR
pipeline) and by the on-demand metadata suggestion endpoint, so the behaviour
stays identical in both places.
"""

import logging
from datetime import datetime, timezone

from app.models.document import Document
from app.services.ollama_classification import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OllamaClassificationError,
    OllamaClassificationInput,
    OllamaClassificationService,
)

logger = logging.getLogger("papermind.ai_classification")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _truncate_error(message: str, max_length: int = 3500) -> str:
    if len(message) <= max_length:
        return message
    return f"{message[:max_length]}..."


def apply_ollama_classification(
    document: Document,
    *,
    extracted_text: str,
    quality_status: str | None,
    confidence_score: float | int | None,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    model: str = DEFAULT_OLLAMA_MODEL,
    allowed_document_types: list[str] | None = None,
    document_type_hints: dict[str, str] | None = None,
) -> str | None:
    """Classify ``document`` and store the result on its ``ai_*`` fields.

    Returns a human-readable warning message when classification was skipped or
    failed, or ``None`` on success. The caller is responsible for committing.
    """
    if quality_status not in {"good", "warning"}:
        document.ai_status = "skipped"
        document.ai_processed_at = _now_utc()
        message = "OCR-Qualität zu gering für automatische KI-Klassifizierung."
        logger.warning(
            "ollama classification skipped document_id=%s quality_status=%s",
            document.id,
            quality_status,
        )
        return message

    normalized_text = " ".join(str(extracted_text or "").split()).strip()
    if not normalized_text:
        document.ai_status = "skipped"
        document.ai_processed_at = _now_utc()
        logger.warning("ollama classification skipped document_id=%s reason=empty_ocr_text", document.id)
        return "Kein OCR-Text für automatische KI-Klassifizierung verfügbar."

    service = OllamaClassificationService(
        base_url=base_url,
        model=model,
        allowed_document_types=allowed_document_types,
        document_type_hints=document_type_hints,
    )
    try:
        result = service.classify(
            OllamaClassificationInput(
                document_id=str(document.id),
                ocr_text=normalized_text,
                confidence_score=float(confidence_score) if isinstance(confidence_score, (int, float)) else None,
                quality_status=quality_status,
            )
        )
    except OllamaClassificationError as exc:
        document.ai_status = "error"
        document.ai_processed_at = _now_utc()
        existing_flags = dict(document.flags or {})
        ai_flags = dict(existing_flags.get("ai_classification") or {})
        ai_flags["error"] = _truncate_error(str(exc), 1000)
        existing_flags["ai_classification"] = ai_flags
        document.flags = existing_flags
        logger.warning("ollama classification failed document_id=%s error=%s", document.id, exc)
        return f"Ollama-Klassifizierung fehlgeschlagen: {_truncate_error(str(exc), 240)}"

    document.ai_document_type = result.document_type
    document.ai_document_date = result.document_date
    document.ai_sender = result.sender
    document.ai_recipient = result.recipient
    document.ai_amount = result.amount
    document.ai_currency = result.currency
    document.ai_summary = result.summary
    document.ai_suggested_tags = result.tags
    document.ai_confidence = result.confidence
    document.ai_status = "done"
    document.ai_processed_at = _now_utc()
    existing_flags = dict(document.flags or {})
    existing_flags["ai_classification"] = {
        "model": model,
        "raw_response": result.raw_response[:4000],
    }
    document.flags = existing_flags
    logger.info(
        "ollama classification completed document_id=%s type=%s confidence=%s tags=%s",
        document.id,
        result.document_type,
        result.confidence,
        result.tags,
    )
    return None

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.document import Document
from app.models.document_retention import DocumentRetention
from app.schemas.retention import (
    RETENTION_PERIOD_UNLIMITED,
    DocumentRetentionRead,
    DocumentRetentionUpdateRequest,
    RetentionPaperOriginal,
    RetentionStatus,
)
from app.services.retention_classification import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OllamaRetentionError,
    OllamaRetentionInput,
    OllamaRetentionRule,
    OllamaRetentionService,
)
from app.services.settings import SettingsService

logger = logging.getLogger("papermind.retention")


def _classify_retention(
    runtime_settings: dict,
    *,
    ocr_text: str,
    document_type: str | None,
    tags: tuple[str, ...],
    document_id: str,
):
    """Führe die reine KI-Aufbewahrungsbewertung aus (ohne persistiertes Dokument).

    Baut den Ollama-Dienst aus den Laufzeit-Settings, sucht die passende Hausregel
    und ruft den Klassifikator. Wirft ``OllamaRetentionError`` bei Modell-/Netzfehlern.
    """
    ollama_cfg = runtime_settings.get("ollama") or {}
    retention_cfg = runtime_settings.get("retention") or {}
    usage_mode = retention_cfg.get("usage_mode") or "business"
    matched_rule = _match_retention_rule(retention_cfg.get("rules"), document_type)
    service = OllamaRetentionService(
        base_url=str(ollama_cfg.get("base_url") or DEFAULT_OLLAMA_BASE_URL),
        model=str(ollama_cfg.get("model") or DEFAULT_OLLAMA_MODEL),
        timeout_seconds=float(ollama_cfg.get("timeout_seconds") or OLLAMA_TIMEOUT_SECONDS),
    )
    return service.classify(
        OllamaRetentionInput(
            document_id=document_id,
            ocr_text=ocr_text,
            document_type=document_type,
            tags=tuple(tags),
            usage_mode=usage_mode,
            rule=matched_rule,
        )
    )


def evaluate_retention_suggestion(
    runtime_settings: dict,
    *,
    ocr_text: str,
    document_type: str | None = None,
    tags: tuple[str, ...] = (),
    document_date: date | None = None,
    document_id: str = "staging",
) -> dict | None:
    """Best-effort-KI-Aufbewahrungsvorschlag für den Import (kein Dokument nötig).

    Gibt ``None`` zurück, wenn Aufbewahrung oder Ollama deaktiviert sind, kein Text
    vorliegt oder die Bewertung fehlschlägt – der Import darf dadurch nie blockieren.
    """
    retention_cfg = runtime_settings.get("retention") or {}
    if retention_cfg.get("enabled") is False:
        return None
    text_value = " ".join(str(ocr_text or "").split()).strip()
    if not text_value:
        return None
    ollama_cfg = runtime_settings.get("ollama") or {}
    if not ollama_cfg.get("enabled"):
        return None
    try:
        result = _classify_retention(
            runtime_settings,
            ocr_text=text_value,
            document_type=document_type,
            tags=tuple(tags),
            document_id=document_id,
        )
    except OllamaRetentionError as exc:
        logger.warning("import retention suggestion failed document_id=%s err=%s", document_id, exc)
        return None
    retain_until = _compute_retain_until(document_date, result.period_years)
    return {
        "paper_original": result.paper_original,
        "period_years": result.period_years,
        "retain_until": retain_until.isoformat() if retain_until else None,
        "reason": result.reason,
        "status": RetentionStatus.suggested.value,
    }


def _match_retention_rule(rules: list | None, document_type: str | None) -> OllamaRetentionRule | None:
    """Finde die kuratierte Hausregel für den Dokumenttyp (case-insensitiv)."""
    if not rules or not document_type:
        return None
    target = " ".join(str(document_type).split()).strip().casefold()
    if not target:
        return None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_type = " ".join(str(rule.get("document_type") or "").split()).strip().casefold()
        if rule_type and rule_type == target:
            return OllamaRetentionRule(
                paper_original=str(rule.get("paper_original") or "unclear"),
                period_years=rule.get("period_years"),
                basis=str(rule.get("basis") or ""),
            )
    return None


def _compute_retain_until(document_date: date | None, period_years: int | None) -> date | None:
    if document_date is None or period_years is None or period_years == RETENTION_PERIOD_UNLIMITED:
        return None
    try:
        return document_date.replace(year=document_date.year + period_years)
    except ValueError:
        # 29. Februar auf einem Referenzjahr ohne Schaltjahr.
        return document_date.replace(month=2, day=28, year=document_date.year + period_years)


class DocumentRetentionService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _get_document(self, document_id: uuid.UUID) -> Document:
        stmt = select(Document).where(Document.id == document_id)
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        document = self.db.execute(stmt).scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})
        return document

    def _get_record(self, document_id: uuid.UUID) -> DocumentRetention | None:
        return self.db.execute(
            select(DocumentRetention).where(DocumentRetention.document_id == document_id)
        ).scalar_one_or_none()

    def _ensure_retention_enabled(self) -> dict:
        runtime_settings = SettingsService(self.db).get_settings().model_dump(mode="json")
        retention_cfg = runtime_settings.get("retention") or {}
        if retention_cfg.get("enabled") is False:
            raise ForbiddenError(
                "Aufbewahrung ist in den Einstellungen deaktiviert.",
            )
        return runtime_settings

    def get_retention(self, document_id: uuid.UUID) -> DocumentRetentionRead:
        self._get_document(document_id)
        self._ensure_retention_enabled()
        record = self._get_record(document_id)
        if record is None:
            return DocumentRetentionRead(document_id=document_id)
        return DocumentRetentionRead.model_validate(record)

    def update_retention(self, document_id: uuid.UUID, payload: DocumentRetentionUpdateRequest) -> DocumentRetentionRead:
        document = self._get_document(document_id)
        self._ensure_retention_enabled()
        record = self._get_record(document_id)
        if record is None:
            record = DocumentRetention(document_id=document_id)
            self.db.add(record)

        record.status = payload.status.value
        record.period_years = payload.period_years
        record.paper_original = payload.paper_original.value
        record.reason = payload.reason
        record.retain_until = _compute_retain_until(document.document_date, payload.period_years)
        record.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(record)
        return DocumentRetentionRead.model_validate(record)

    def accept_suggestion(self, document_id: uuid.UUID) -> DocumentRetentionRead:
        self._get_document(document_id)
        self._ensure_retention_enabled()
        record = self._get_record(document_id)
        if record is None or record.status != RetentionStatus.suggested.value:
            raise ConflictError(
                "Kein KI-Vorschlag zum Übernehmen vorhanden.",
                details={"document_id": str(document_id)},
            )
        record.status = RetentionStatus.accepted.value
        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return DocumentRetentionRead.model_validate(record)

    def discard_suggestion(self, document_id: uuid.UUID) -> DocumentRetentionRead:
        self._get_document(document_id)
        self._ensure_retention_enabled()
        record = self._get_record(document_id)
        if record is None or record.status != RetentionStatus.suggested.value:
            raise ConflictError(
                "Kein KI-Vorschlag zum Verwerfen vorhanden.",
                details={"document_id": str(document_id)},
            )
        record.status = RetentionStatus.not_evaluated.value
        record.paper_original = RetentionPaperOriginal.unclear.value
        record.period_years = None
        record.retain_until = None
        record.reason = None
        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return DocumentRetentionRead.model_validate(record)

    def suggest_retention(self, document_id: uuid.UUID) -> DocumentRetentionRead:
        document = self._get_document(document_id)
        runtime_settings = self._ensure_retention_enabled()

        text_value = " ".join(str(document.text_content or "").split()).strip()
        if not text_value:
            raise ConflictError(
                "KI-Bewertung nicht möglich, weil kein extrahierbarer Text verfügbar ist.",
                details={"document_id": str(document_id)},
            )

        ollama_cfg = runtime_settings.get("ollama") or {}
        if not ollama_cfg.get("enabled"):
            raise ConflictError(
                "KI-Aufbewahrungsbewertung ist in den Einstellungen deaktiviert.",
                details={"document_id": str(document_id)},
            )

        tag_names = tuple(tag.name for tag in (document.tags or []) if getattr(tag, "name", None))
        try:
            result = _classify_retention(
                runtime_settings,
                ocr_text=text_value,
                document_type=document.document_type,
                tags=tag_names,
                document_id=str(document.id),
            )
        except OllamaRetentionError as exc:
            raise ConflictError(
                f"KI-Aufbewahrungsbewertung fehlgeschlagen: {exc}",
                details={"document_id": str(document_id)},
            ) from exc

        record = self._get_record(document_id)
        if record is None:
            record = DocumentRetention(document_id=document_id)
            self.db.add(record)

        record.status = RetentionStatus.suggested.value
        record.paper_original = result.paper_original
        record.period_years = result.period_years
        record.reason = result.reason
        record.retain_until = _compute_retain_until(document.document_date, result.period_years)
        record.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(record)
        return DocumentRetentionRead.model_validate(record)

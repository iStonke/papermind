"""Zentrale Zustandsübergänge beim Einreihen von Dokument-Jobs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.document import Document
from app.models.job import Job
from app.services.job_queue import enqueue_document_job, has_active_document_job


class DocumentJobLifecycleService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def has_active(self, document_id, job_type: str) -> bool:
        return has_active_document_job(self.db, document_id, job_type)

    def queue_index(self, document: Document) -> bool:
        if enqueue_document_job(self.db, document.id, "INDEX") is None:
            return False
        document.embedding_status = "queued"
        return True

    def queue_tag(self, document: Document) -> bool:
        return enqueue_document_job(self.db, document.id, "TAG") is not None

    def queue_ocr(self, document: Document) -> Job:
        if self.has_active(document.id, "OCR"):
            raise ConflictError("OCR job is already queued or running for this document", details={"document_id": str(document.id)})
        if document.flags and document.flags.get("ocr_retry_blocked"):
            flags = dict(document.flags)
            flags.pop("ocr_retry_blocked", None)
            document.flags = flags or None
        job = enqueue_document_job(self.db, document.id, "OCR")
        if job is None:
            raise ConflictError("OCR job is already queued or running for this document", details={"document_id": str(document.id)})
        document.status = "processing"
        document.ocr_status = "queued"
        document.ocr_quality_status = None
        document.ocr_confidence_score = None
        document.ocr_quality_message = None
        document.ocr_processing_seconds = None
        document.ai_status = "pending"
        document.ai_document_type = None
        document.ai_document_date = None
        document.ai_sender = None
        document.ai_recipient = None
        document.ai_amount = None
        document.ai_currency = None
        document.ai_summary = None
        document.ai_suggested_tags = None
        document.ai_confidence = None
        document.ai_processed_at = None
        return job

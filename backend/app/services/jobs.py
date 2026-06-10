import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.document import Document
from app.models.job import Job
from app.schemas.jobs import JobCreateRequest, JobUpdateRequest

logger = logging.getLogger("papermind.jobs")


class JobService:
    def __init__(self, db: Session, owner_id: uuid.UUID | None = None):
        self.db = db
        self.owner_id = owner_id

    def _ensure_document_exists(self, document_id: uuid.UUID) -> None:
        stmt = select(Document.id).where(Document.id == document_id)
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        exists = self.db.execute(stmt).scalar_one_or_none()
        if exists is None:
            raise NotFoundError("Document not found", details={"document_id": str(document_id)})

    def list_document_jobs(self, document_id: uuid.UUID) -> list[Job]:
        self._ensure_document_exists(document_id)
        stmt = select(Job).where(Job.document_id == document_id).order_by(Job.created_at.desc())
        return self.db.execute(stmt).scalars().all()

    def create_document_job(self, document_id: uuid.UUID, payload: JobCreateRequest) -> Job:
        self._ensure_document_exists(document_id)
        if payload.type.value in {"OCR", "INDEX", "TAG"}:
            active_job = self.db.execute(
                select(Job.id).where(
                    Job.document_id == document_id,
                    Job.type == payload.type.value,
                    Job.status.in_(("queued", "running")),
                )
            ).scalar_one_or_none()
            if active_job is not None:
                raise ConflictError(
                    f"{payload.type.value} job is already queued or running for this document",
                    details={"document_id": str(document_id), "type": payload.type.value},
                )

        job = Job(document_id=document_id, type=payload.type.value, status="queued")
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        logger.info("job created id=%s document_id=%s type=%s", job.id, document_id, payload.type.value)
        return job

    def get_job_or_404(self, job_id: uuid.UUID) -> Job:
        job = self.db.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found", details={"job_id": str(job_id)})
        if self.owner_id is not None:
            owner = self.db.execute(
                select(Document.owner_id).where(Document.id == job.document_id)
            ).scalar_one_or_none()
            if owner != self.owner_id:
                raise NotFoundError("Job not found", details={"job_id": str(job_id)})
        return job

    def update_job(self, job_id: uuid.UUID, payload: JobUpdateRequest) -> Job:
        job = self.get_job_or_404(job_id)
        data = payload.model_dump(exclude_unset=True)

        if "status" in data and data["status"] is not None:
            job.status = data["status"].value
            if data["status"].value == "running" and job.started_at is None:
                job.started_at = datetime.now(timezone.utc)
            if data["status"].value in {"done", "failed"}:
                job.finished_at = datetime.now(timezone.utc)
        if "progress" in data:
            job.progress = data["progress"]
        if "error_message" in data:
            job.error_message = data["error_message"]

        self.db.commit()
        self.db.refresh(job)
        logger.info("job updated id=%s", job_id)
        return job

    def get_activity(self, *, failed_window_hours: int = 24, limit: int = 100) -> dict:
        """Aktive (queued/running) sowie kürzlich fehlgeschlagene Jobs für die
        Header-Aktivitätsanzeige – inkl. Dokumenttitel und Zähler.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=failed_window_hours)
        status_order = case(
            (Job.status == "running", 0),
            (Job.status == "queued", 1),
            else_=2,
        )
        stmt = (
            select(Job, func.coalesce(Document.display_name, Document.original_filename))
            .join(Document, Document.id == Job.document_id)
            .where(
                or_(
                    Job.status.in_(("queued", "running")),
                    and_(Job.status == "failed", Job.updated_at >= cutoff),
                )
            )
            .order_by(status_order, Job.created_at.desc())
            .limit(limit)
        )
        if self.owner_id is not None:
            stmt = stmt.where(Document.owner_id == self.owner_id)
        rows = self.db.execute(stmt).all()
        summary = {"queued": 0, "running": 0, "failed": 0}
        items: list[dict] = []
        for job, title in rows:
            if job.status in summary:
                summary[job.status] += 1
            items.append({"job": job, "document_title": title})

        # Dokument-Ebene: Gesamtfortschritt der Volltext-Erkennung. Unabhängig von
        # einzelnen Jobs, damit der Backlog auch zwischen den OCR-Häppchen sichtbar
        # ist.
        backlog_stmt = (
            select(Document.ocr_status, func.count(Document.id))
            .where(Document.is_deleted.is_(False))
            .group_by(Document.ocr_status)
        )
        if self.owner_id is not None:
            backlog_stmt = backlog_stmt.where(Document.owner_id == self.owner_id)
        status_rows = self.db.execute(backlog_stmt).all()
        status_counts = {str(status): int(count) for status, count in status_rows}
        total = sum(status_counts.values())
        done = status_counts.get("done", 0)
        failed_docs = status_counts.get("failed", 0)
        ocr_backlog = {
            "total": total,
            "done": done,
            "failed": failed_docs,
            "pending": max(0, total - done - failed_docs),
        }
        return {
            "summary": summary,
            "jobs": items,
            "ocr_backlog": ocr_backlog,
            "backup": self._backup_activity(),
        }

    def _backup_activity(self) -> dict | None:
        """Backup-Fehler für die Header-Aktivität: nur wenn Backup aktiviert ist und
        der zuletzt gestartete Lauf fehlgeschlagen ist. Fehler hier dürfen die
        Aktivitätsanzeige nie blockieren."""
        from app.models.backup_run import BackupRun
        from app.services.backup import BackupService

        try:
            config = BackupService(self.db).get_config()
            if not config.get("enabled"):
                return None
            last = self.db.execute(
                select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1)
            ).scalar_one_or_none()
            if last is None or last.status != "failed":
                return None
            return {"status": "failed", "error": last.error, "finished_at": last.finished_at}
        except Exception:  # noqa: BLE001 - Aktivität ist best effort
            logger.warning("backup activity check failed", exc_info=True)
            return None

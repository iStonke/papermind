import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.document import Document
from app.models.job import Job
from app.schemas.jobs import JobCreateRequest, JobUpdateRequest

logger = logging.getLogger("papermind.jobs")


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_document_exists(self, document_id: uuid.UUID) -> None:
        exists = self.db.execute(select(Document.id).where(Document.id == document_id)).scalar_one_or_none()
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

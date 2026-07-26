"""Gemeinsame, transaktionsneutrale Queue-Helfer für Dokument-Jobs."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job

ACTIVE_JOB_STATUSES = ("queued", "running")


def has_active_document_job(db: Session, document_id: uuid.UUID, job_type: str) -> bool:
    return (
        db.execute(
            select(Job.id).where(
                Job.document_id == document_id,
                Job.type == job_type,
                Job.status.in_(ACTIVE_JOB_STATUSES),
            )
        ).scalar_one_or_none()
        is not None
    )


def enqueue_document_job(db: Session, document_id: uuid.UUID, job_type: str) -> Job | None:
    if has_active_document_job(db, document_id, job_type):
        return None
    job = Job(document_id=document_id, type=job_type, status="queued", progress=0)
    db.add(job)
    return job

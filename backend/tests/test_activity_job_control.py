import uuid

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.job import Job
from app.services.jobs import JobService
from test_index_transactions import indexed_source
from test_job_publication import running_job


def test_cancel_revokes_lease_blocks_backfill_and_can_restart(indexed_source):
    doc_id, _, _ = indexed_source
    job_id, token = running_job(doc_id, 'OCR')
    with SessionLocal() as db:
        owner = db.get(Document, doc_id).owner_id
        service = JobService(db, owner)
        cancelled = service.control_job(job_id, action='cancel')
        assert cancelled.status == 'failed'
        assert cancelled.lease_token is None
        assert db.get(Document, doc_id).flags['ocr_retry_blocked']
        assert db.scalar(select(Job.id).where(Job.id == job_id, Job.lease_token == token)) is None
        restarted = service.control_job(job_id, action='restart')
        assert restarted.status == 'queued'
        assert not (db.get(Document, doc_id).flags or {}).get('ocr_retry_blocked')


def test_control_is_owner_scoped(indexed_source):
    doc_id, _, _ = indexed_source
    job_id, _ = running_job(doc_id, 'TAG')
    with SessionLocal() as db:
        with pytest.raises(NotFoundError):
            JobService(db, uuid.uuid4()).control_job(job_id, action='cancel')
        db.rollback()
        assert db.get(Job, job_id).status == 'running'


def test_terminal_cancel_is_a_conflict(indexed_source):
    doc_id, _, _ = indexed_source
    job_id, _ = running_job(doc_id, 'INDEX')
    with SessionLocal() as db:
        service = JobService(db, db.get(Document, doc_id).owner_id)
        service.control_job(job_id, action='cancel')
        with pytest.raises(ConflictError):
            service.control_job(job_id, action='cancel')

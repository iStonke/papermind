import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.job import Job
from app.services.jobs import JobService
from app.worker import main as worker
from app.worker.ocr_isolation import OCRAborted, OCRDeadlineExceeded
from test_index_transactions import indexed_source  # noqa: F401 - Fixture


def _job(doc_id, *, status="running", attempts=1, lease_expired=False):
    token = uuid.uuid4()
    expires = datetime.now(timezone.utc) + (timedelta(minutes=-1) if lease_expired else timedelta(minutes=5))
    with SessionLocal() as db:
        job = Job(document_id=doc_id, type="OCR", status=status, attempts=attempts, lease_token=token,
                  lease_expires_at=expires)
        db.add(job)
        db.commit()
        return job.id, token


def _patched_storage(source):
    return patch.object(worker, "_resolve_storage_path", side_effect=lambda key: source.parent / key.split("/")[-1])


def test_ocr_deadline_marks_job_timed_out_and_blocks_backfill(indexed_source):
    doc_id, _, source = indexed_source
    job_id, token = _job(doc_id)
    guard = worker.JobGuard("OCR")

    with _patched_storage(source), patch.object(worker, "_count_pdf_pages", return_value=3), patch.object(
        worker, "_run_ocr_pipeline_isolated", side_effect=OCRDeadlineExceeded("zu lange")
    ):
        worker._process_ocr_job(job_id, token, guard)

    assert guard.page_count == 3
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        document = db.get(Document, doc_id)
        assert job.status == "failed"
        assert job.failure_kind == "timeout"
        assert job.error_message.startswith("Automatisch beendet: Die Texterkennung lief länger als")
        assert "Grenze für 3 Seiten" in job.error_message
        assert job.lease_token is None
        assert document.ocr_status == "failed"
        assert document.flags["ocr_retry_blocked"] is True


def test_ocr_abort_leaves_status_to_whoever_aborted(indexed_source):
    doc_id, _, source = indexed_source
    job_id, token = _job(doc_id)
    with _patched_storage(source), patch.object(
        worker, "_run_ocr_pipeline_isolated", side_effect=OCRAborted("abgebrochen")
    ):
        worker._process_ocr_job(job_id, token, worker.JobGuard("OCR"))
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.status == "running"
        assert job.failure_kind is None


def test_ocr_deadline_scales_with_pages_and_is_capped():
    settings = worker.settings
    assert worker._ocr_deadline_seconds(2) == settings.worker_ocr_deadline_base_seconds + 2 * settings.worker_ocr_deadline_per_page_seconds
    assert worker._ocr_deadline_seconds(10_000) == settings.worker_ocr_deadline_max_seconds


def test_heartbeat_ends_job_after_deadline(indexed_source):
    doc_id, _, _ = indexed_source
    job_id, token = _job(doc_id)
    guard = worker.JobGuard("TAG", deadline_seconds=1)
    with patch.object(worker.settings, "worker_job_heartbeat_seconds", 5):
        with worker._job_lease_heartbeat(job_id, token, guard):
            assert guard.aborted.wait(15)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.status == "failed"
        assert job.failure_kind == "timeout"
        assert job.error_message.startswith("Automatisch beendet: Der Vorgang lief länger als")


@pytest.mark.parametrize("attempts, expected", [(1, "queued"), (3, "failed")])
def test_reclaim_stops_after_max_attempts(indexed_source, attempts, expected):
    doc_id, _, _ = indexed_source
    job_id, _ = _job(doc_id, attempts=attempts, lease_expired=True)
    with patch.object(worker.settings, "worker_job_max_attempts", 3):
        worker._reclaim_orphaned_jobs()
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        document = db.get(Document, doc_id)
        assert job.status == expected
        if expected == "failed":
            assert job.failure_kind == "retry_limit"
            assert "3× unterbrochen" in job.error_message
            assert document.ocr_status == "failed"
            assert document.flags["ocr_retry_blocked"] is True
        else:
            assert job.failure_kind is None
            assert not (document.flags or {}).get("ocr_retry_blocked")


def test_user_restart_resets_attempts_and_failure_kind(indexed_source):
    doc_id, _, _ = indexed_source
    job_id, _ = _job(doc_id, status="failed", attempts=3)
    with SessionLocal() as db:
        db.get(Job, job_id).failure_kind = "timeout"
        document = db.get(Document, doc_id)
        document.flags = {"ocr_retry_blocked": True}
        db.commit()
        job = JobService(db).control_job(job_id, action="restart")
        assert job.status == "queued"
        assert job.attempts == 0
        assert job.failure_kind is None
        assert not (db.get(Document, doc_id).flags or {}).get("ocr_retry_blocked")

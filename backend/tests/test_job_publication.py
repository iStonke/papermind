import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.job import Job
from app.services.embeddings import EmbeddingService, settings
from app.worker import main as worker
from test_index_transactions import indexed_source


def running_job(doc_id, kind):
    token = uuid.uuid4()
    with SessionLocal() as db:
        job = Job(document_id=doc_id, type=kind, status="running", lease_token=token,
                  lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        db.add(job)
        db.commit()
        return job.id, token


def steal_job(job_id):
    with SessionLocal() as db:
        db.execute(text("UPDATE jobs SET lease_token=:token WHERE id=:id"),
                   {"token": uuid.uuid4(), "id": job_id})
        db.commit()


def test_index_lease_loss_does_not_commit_chunks(indexed_source):
    doc_id, _, source = indexed_source
    job_id, token = running_job(doc_id, "INDEX")
    with SessionLocal() as db:
        service = EmbeddingService(db)

        def embed(texts, model):
            steal_job(job_id)
            return model, settings.embed_dim, [[1.0] * settings.embed_dim for _ in texts], 1.0

        with patch.object(service, "_resolve_storage_path", return_value=source), patch.object(
            service, "_extract_page_texts", return_value=("Invoice text " * 60, [], True, [])
        ), patch.object(service, "_embed_text_batch", side_effect=embed), pytest.raises(RuntimeError, match="lease lost"):
            service.index_document(doc_id, publish_guard=lambda: worker._require_job_lease(db, job_id, token))
        assert db.scalar(text("SELECT count(*) FROM doc_chunks WHERE doc_id=:id"), {"id": doc_id}) == 0


@pytest.mark.parametrize("lose_lease", [False, True])
def test_ocr_attempt_publishes_only_with_lease_and_preserves_old_pdf(indexed_source, lose_lease):
    doc_id, _, source = indexed_source
    old_pdf = source.parent / "ocr.pdf"
    old_pdf.write_bytes(b"previous valid OCR")
    with SessionLocal() as db:
        db.add(DocumentFile(document_id=doc_id, role="ocr", file_key="ocr.pdf", mime_type="application/pdf"))
        db.commit()
    job_id, token = running_job(doc_id, "OCR")

    def pipeline(original, output, runtime, **kwargs):
        output.write_bytes(b"new OCR result")
        if lose_lease:
            steal_job(job_id)
        return {"text": "Invoice text", "pages": [], "page_count": 1, "quality_status": "good"}

    with patch.object(worker, "_resolve_storage_path", side_effect=lambda key: source.parent / key.split("/")[-1]), patch.object(
        worker, "run_ocr_pipeline", side_effect=pipeline
    ), patch.object(worker, "apply_ollama_classification", return_value=None):
        worker._process_ocr_job(job_id, token)
    assert old_pdf.read_bytes() == b"previous valid OCR"
    with SessionLocal() as db:
        file = db.scalar(select(DocumentFile).where(DocumentFile.document_id == doc_id, DocumentFile.role == "ocr"))
        if lose_lease:
            assert file.file_key == "ocr.pdf"
            assert db.get(Job, job_id).status == "running"
        else:
            assert file.file_key.endswith(f"ocr-{token.hex}.pdf")
            assert (source.parent / file.file_key.split("/")[-1]).read_bytes() == b"new OCR result"
            assert db.get(Job, job_id).status == "done"
            assert db.get(Document, doc_id).text_content == "Invoice text"
    assert not list(source.parent.glob(".ocr-attempt-*"))

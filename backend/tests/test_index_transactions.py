"""Real PostgreSQL regression tests for long-running indexing and backup dirtiness."""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.errors import ConflictError
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.user import User
from app.services.backup import BackupService
from app.services.embeddings import EmbeddingService, settings


@pytest.fixture
def indexed_source(tmp_path):
    with SessionLocal() as db:
        user = User(username=f"index-test-{uuid.uuid4().hex}", password_hash="x")
        db.add(user)
        db.flush()
        doc = Document(owner_id=user.id, original_filename="test.pdf")
        db.add(doc)
        db.flush()
        db.add(DocumentFile(document_id=doc.id, role="original", file_key="test.pdf", mime_type="application/pdf"))
        db.commit()
        doc_id, user_id = doc.id, user.id
    source = tmp_path / "test.pdf"
    source.write_bytes(b"original source")
    try:
        yield doc_id, user_id, source
    finally:
        with SessionLocal() as db:
            db.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            db.commit()


def test_embedding_call_has_no_open_transaction_and_allows_unrelated_write(indexed_source):
    doc_id, user_id, source = indexed_source
    with SessionLocal() as db:
        service = EmbeddingService(db)

        def embed(texts, model):
            assert not db.in_transaction()
            with SessionLocal() as other:
                other.execute(text("SET LOCAL lock_timeout = '300ms'"))
                other.execute(text("UPDATE users SET email='index-test@example.test' WHERE id=:id"), {"id": user_id})
                other.commit()
            return model, settings.embed_dim, [[1.0] + [0.0] * (settings.embed_dim - 1) for _ in texts], 1.0

        with patch.object(service, "_resolve_storage_path", return_value=source), patch.object(
            service, "_extract_page_texts", return_value=("Invoice text " * 60, [], True, [])
        ), patch.object(service, "_embed_text_batch", side_effect=embed):
            result = service.index_document(doc_id)
        assert result["chunk_count"] > 0
        assert db.scalar(text("SELECT count(*) FROM doc_embeddings e JOIN doc_chunks c ON c.id=e.chunk_id WHERE c.doc_id=:id"), {"id": doc_id}) > 0


def test_source_change_during_embedding_does_not_publish(indexed_source):
    doc_id, _, source = indexed_source
    with SessionLocal() as db:
        service = EmbeddingService(db)

        def embed(texts, model):
            source.write_bytes(b"changed source")
            return model, settings.embed_dim, [[1.0] * settings.embed_dim for _ in texts], 1.0

        with patch.object(service, "_resolve_storage_path", return_value=source), patch.object(
            service, "_extract_page_texts", return_value=("Invoice text " * 60, [], True, [])
        ), patch.object(service, "_embed_text_batch", side_effect=embed), pytest.raises(ConflictError):
            service.index_document(doc_id)
        assert db.scalar(text("SELECT count(*) FROM doc_chunks WHERE doc_id=:id"), {"id": doc_id}) == 0


def test_dirty_transactions_do_not_block_each_other_or_lose_late_commits(indexed_source):
    _, user_id, _ = indexed_source
    with SessionLocal() as delayed, SessionLocal() as other:
        delayed.execute(text("UPDATE users SET email='late@example.test' WHERE id=:id"), {"id": user_id})
        other.execute(text("SET LOCAL lock_timeout = '300ms'"))
        # A different source table must remain writable while the first is open.
        other.execute(text("UPDATE global_settings SET settings_json=settings_json WHERE id=1"))
        other.commit()
        service = BackupService(other)
        state = service._source_state()
        service._mark_source_backed_up(state.generation)
        other.commit()
        clean = service._source_state()
        assert clean.generation == clean.backed_up_generation
        delayed.commit()
        dirty = service._source_state()
        assert dirty.generation > dirty.backed_up_generation

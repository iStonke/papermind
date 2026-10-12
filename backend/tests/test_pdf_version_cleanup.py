import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.document import Document
from app.models.document_file import DocumentFile
from app.models.job import Job
from app.models.user import User
from app.services.maintenance import maintenance_mode
from app.services.pdf_version_cleanup import cleanup_pdf_versions


@pytest.fixture
def document(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), 'storage_path', str(tmp_path))
    with SessionLocal() as db:
        user = User(username='cleanup-' + uuid.uuid4().hex, password_hash='x', is_active=True)
        db.add(user); db.flush()
        doc = Document(owner_id=user.id, original_filename='source.pdf')
        db.add(doc); db.commit()
        user_id, document_id = user.id, doc.id
    directory = tmp_path / str(document_id); directory.mkdir()
    yield document_id, directory
    with SessionLocal() as db:
        db.execute(text('DELETE FROM users WHERE id=:id'), {'id': user_id}); db.commit()


def version(directory, *, days=20, name=None):
    path = directory / (name or 'ocr-' + uuid.uuid4().hex + '.pdf')
    path.write_bytes(b'private document version')
    timestamp = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    os.utime(path, (timestamp, timestamp))
    return path


def cleanup(root, **kwargs):
    with SessionLocal() as db:
        return cleanup_pdf_versions(db, root, **kwargs)


def test_only_old_unreferenced_generated_versions_are_deleted(document):
    identifier, directory = document
    old = version(directory)
    recent = version(directory, days=2)
    legacy = version(directory, name='original.pdf')
    unknown = version(directory, name='private.pdf')
    assert cleanup(directory.parent) == 1
    assert not old.exists()
    assert all(path.exists() for path in (recent, legacy, unknown))


def test_current_references_and_trash_are_preserved(document):
    identifier, directory = document
    current = version(directory); original = version(directory)
    with SessionLocal() as db:
        doc = db.get(Document, identifier); doc.is_deleted = True
        doc.storage_key = str(original.relative_to(directory.parent))
        db.add(DocumentFile(document_id=identifier, role='ocr', file_key=str(current.relative_to(directory.parent)), mime_type='application/pdf'))
        db.commit()
    assert cleanup(directory.parent) == 0
    assert current.exists() and original.exists()


def test_legacy_reference_from_another_document_is_preserved(document):
    identifier, directory = document; referenced = version(directory)
    with SessionLocal() as db:
        other = Document(owner_id=db.get(Document,identifier).owner_id, original_filename='legacy.pdf')
        db.add(other);db.flush()
        db.add(DocumentFile(document_id=other.id,role='original',mime_type='application/pdf',
            file_key=str(referenced.relative_to(directory.parent))))
        db.commit()
    assert cleanup(directory.parent)==0
    assert referenced.exists()


@pytest.mark.parametrize('status', ['queued', 'running'])
def test_active_job_retains_unpublished_versions(document, status):
    identifier, directory = document; old = version(directory)
    with SessionLocal() as db:
        db.add(Job(document_id=identifier, type='OCR', status=status)); db.commit()
    assert cleanup(directory.parent) == 0
    assert old.exists()


def test_symlinks_never_delete_external_files(document, tmp_path):
    identifier, directory = document
    external = tmp_path / 'outside.pdf'; external.write_bytes(b'preserve')
    link = directory / ('ocr-' + uuid.uuid4().hex + '.pdf'); link.symlink_to(external)
    assert cleanup(directory.parent) == 0
    assert external.read_bytes() == b'preserve' and link.is_symlink()
    directory.rename(tmp_path / 'real-document')
    directory.symlink_to(tmp_path / 'real-document', target_is_directory=True)
    version(tmp_path / 'real-document')
    assert cleanup(directory.parent) == 0


def test_locked_document_is_skipped_during_publication(document):
    identifier, directory = document; old = version(directory)
    with SessionLocal() as publishing:
        publishing.execute(select(Document).where(Document.id == identifier).with_for_update()).scalar_one()
        assert cleanup(directory.parent) == 0
        assert old.exists()


def test_cleanup_obeys_file_budget(document):
    _, directory = document
    versions = [version(directory) for _ in range(3)]
    assert cleanup(directory.parent, max_files=1) == 1
    assert sum(path.exists() for path in versions) == 2


def test_backup_maintenance_prevents_cleanup(document):
    _, directory = document; old = version(directory)
    with maintenance_mode('test_backup'):
        assert cleanup(directory.parent) == 0
    assert old.exists()

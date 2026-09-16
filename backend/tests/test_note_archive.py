import copy
import io
import uuid

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.notes import NoteCreateRequest, NoteUpdateRequest
from app.services.note_service import NoteService
from app.services.note_images import NoteImageService, NoteImageStorage
from app.services.note_archive import NoteArchiveService, NoteArchive
from app.core.errors import BadRequestError, NotFoundError


@pytest.fixture
def archive_service(tmp_path):
    db = SessionLocal()
    user = User(username=f'archive-{uuid.uuid4().hex}', password_hash='x', is_active=True)
    db.add(user)
    db.commit()
    owner_id = user.id
    service = NoteArchiveService(db, owner_id)
    service.storage = NoteImageStorage(storage_path=str(tmp_path))
    try:
        yield service
    finally:
        db.rollback()
        db.execute(text('DELETE FROM users WHERE id = :id'), {'id': owner_id})
        db.commit()
        db.close()


def test_round_trip_preserves_content_history_metadata_and_image_bytes(archive_service):
    svc = archive_service
    note = svc.notes.create_note(NoteCreateRequest(title='Äöü – vollständig'))
    images = NoteImageService(svc.db, svc.owner_id)
    images.storage = svc.storage
    raw = io.BytesIO()
    Image.new('RGB', (10, 12), 'red').save(raw, format='PNG')
    raw.seek(0)
    image = images.upload(note.id, UploadFile(filename='Bild.png', file=raw, headers={'content-type': 'image/png'}))
    body = {'type': 'doc', 'attrs': {'layout': 'wide'}, 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Hallo', 'marks': [{'type': 'bold'}]}]},
        {'type': 'image', 'attrs': {'imageId': str(image.id), 'noteId': str(note.id), 'src': images.image_src(note.id, image.id), 'caption': 'Bild', 'width': 123}},
        {'type': 'taskList', 'content': [{'type': 'taskItem', 'attrs': {'checked': True}, 'content': [{'type': 'paragraph'}]}]},
    ]}
    svc.notes.update_note(note.id, NoteUpdateRequest(body_json=body, is_favorite=True))
    svc.notes.set_tags(note.id, names=['Test'])
    archive = svc.export(note.id)
    imported = svc.import_archive(NoteArchive.model_validate_json(archive.model_dump_json()))
    result = svc.export(imported.id)
    assert result.source_id != archive.source_id
    assert result.images[0].data == archive.images[0].data
    assert result.images[0].id != archive.images[0].id
    expected_body = copy.deepcopy(body)
    expected_body['content'][1]['attrs'].update(imageId=str(result.images[0].id), noteId=str(imported.id), src=images.image_src(imported.id, result.images[0].id))
    assert result.body_json == expected_body
    for field in ['title', 'tags', 'created_at', 'updated_at', 'revision', 'is_favorite', 'collection', 'notebook']:
        assert getattr(result, field) == getattr(archive, field), field
    assert len(result.history) == len(archive.history)
    assert [v.note_revision for v in result.history] == [v.note_revision for v in archive.history]
    assert svc.notes.get_note(note.id).body_json == body
    for original, restored in zip(archive.history, result.history):
        assert original.title == restored.title
        assert original.created_at == restored.created_at
        assert original.updated_at == restored.updated_at
        assert original.reason == restored.reason
    svc.notes.delete_note(note.id)
    assert svc.export(imported.id).images[0].data == archive.images[0].data


def test_invalid_archive_does_not_create_a_note(archive_service):
    svc = archive_service
    note = svc.notes.create_note(NoteCreateRequest(title='Original'))
    archive = svc.export(note.id)
    archive.body_json = {'type': 'doc', 'content': [{'type': 'image', 'attrs': {'imageId': str(uuid.uuid4())}}]}
    with pytest.raises(BadRequestError):
        svc.import_archive(archive)
    assert len(svc.notes.list_notes()) == 1


def test_export_is_owner_scoped(archive_service):
    note = archive_service.notes.create_note(NoteCreateRequest())
    with pytest.raises(NotFoundError):
        NoteArchiveService(archive_service.db, uuid.uuid4()).export(note.id)


def test_import_rolls_back_database_and_files_on_failure(archive_service, monkeypatch):
    svc = archive_service
    note = svc.notes.create_note(NoteCreateRequest(title='Original'))
    archive = svc.export(note.id)
    def fail(_note):
        raise RuntimeError('simulated failure')
    monkeypatch.setattr(svc.notes, '_sync_tasks', fail)
    with pytest.raises(RuntimeError):
        svc.import_archive(archive)
    assert len(svc.notes.list_notes()) == 1


def test_repeated_import_preserves_notebook_and_history(archive_service):
    from app.services.note_archive import Folder
    svc = archive_service
    note = svc.notes.create_note(NoteCreateRequest(title='Ordner'))
    archive = svc.export(note.id)
    archive.collection = Folder(name='Importierte Sammlung', color='blue', position=2)
    archive.notebook = Folder(name='Notizbuch', color='red', position=3)
    first = svc.import_archive(archive)
    second = svc.import_archive(archive)
    assert first.id != second.id
    assert first.notebook_id == second.notebook_id
    exported = svc.export(second.id)
    assert exported.collection == archive.collection
    assert exported.notebook == archive.notebook
    assert exported.history == archive.history

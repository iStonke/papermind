from types import SimpleNamespace
from uuid import uuid4

from app.services.note_service import NoteService


class FakeSession:
    def __init__(self, notes=None):
        self.notes = list(notes or [])
        self.commits = 0
        self.refreshed = []
        self.deleted = []

    def commit(self):
        self.commits += 1

    def refresh(self, note):
        self.refreshed.append(note)

    def delete(self, note):
        self.deleted.append(note)

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: list(self.notes))


def test_note_moves_to_trash_and_can_be_restored():
    note = SimpleNamespace(is_deleted=False, deleted_at=None)
    db = FakeSession()
    service = NoteService(db, uuid4())
    service._get = lambda _note_id, include_deleted=False: note

    assert service.trash_note(uuid4()) is note
    assert note.is_deleted is True
    assert note.deleted_at is not None

    assert service.restore_note(uuid4()) is note
    assert note.is_deleted is False
    assert note.deleted_at is None
    assert db.commits == 2
    assert db.refreshed == [note, note]


def test_empty_note_trash_permanently_deletes_only_returned_rows():
    notes = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]
    db = FakeSession(notes)
    service = NoteService(db, uuid4())

    assert service.empty_trash() == 2
    assert db.deleted == notes
    assert db.commits == 1

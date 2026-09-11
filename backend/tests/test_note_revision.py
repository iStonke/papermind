from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.errors import ConflictError
from app.schemas.notes import NoteUpdateRequest
from app.services.note_service import NoteService, extract_note_tasks


def _task_doc(*, checked: bool) -> dict:
    return {
        "type": "doc",
        "content": [
            {
                "type": "taskList",
                "content": [
                    {
                        "type": "taskItem",
                        "attrs": {"checked": checked},
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Bericht prüfen"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def refresh(self, note):
        self.refreshed.append(note)

    def add(self, value):
        self.added = getattr(self, "added", [])
        self.added.append(value)


def test_note_update_advances_matching_revision():
    note = SimpleNamespace(
        title="Vorher",
        body_json={"type": "doc", "content": [{"type": "paragraph"}]},
        body_text="",
        is_template=False,
        revision=4,
    )
    db = FakeSession()
    service = NoteService(db, uuid4())
    get_options = []

    def get_note(_note_id, **kwargs):
        get_options.append(kwargs)
        return note

    service._get = get_note
    recorded = []
    service._record_revision = lambda current, **kwargs: recorded.append((current, kwargs))

    result = service.update_note(
        uuid4(),
        NoteUpdateRequest(title="Nachher", base_revision=4),
    )

    assert result is note
    assert note.title == "Nachher"
    assert note.revision == 5
    assert get_options == [{"for_update": True}]
    assert recorded == [(note, {"reason": "autosave"})]
    assert db.commits == 1
    assert db.refreshed == [note]


def test_editor_task_change_updates_dashboard_task_projection():
    note = SimpleNamespace(
        title="Aufgaben",
        body_json=_task_doc(checked=False),
        body_text="Bericht prüfen",
        is_template=False,
        revision=2,
    )
    db = FakeSession()
    service = NoteService(db, uuid4())
    service._get = lambda _note_id, **_kwargs: note
    service._sync_links = lambda _note: None
    projected = []
    service._sync_tasks = lambda current: projected.extend(extract_note_tasks(current.body_json))
    service._record_revision = lambda *_args, **_kwargs: None

    service.update_note(
        uuid4(),
        NoteUpdateRequest(body_json=_task_doc(checked=True), base_revision=2),
    )

    assert projected == [{
        "text": "Bericht prüfen",
        "done": True,
        "due_date": None,
        "position": 0,
    }]


def test_dashboard_task_change_updates_canonical_note_body():
    note = SimpleNamespace(
        title="Aufgaben",
        body_json=_task_doc(checked=False),
        body_text="Bericht prüfen",
        is_template=False,
        revision=2,
    )
    db = FakeSession()
    service = NoteService(db, uuid4())
    service._get = lambda _note_id, **_kwargs: note
    service._sync_links = lambda _note: None
    projected = []
    service._sync_tasks = lambda current: projected.extend(extract_note_tasks(current.body_json))
    service._record_revision = lambda *_args, **_kwargs: None

    result = service.set_task_checked(uuid4(), 0, True)

    assert result is note
    assert note.body_json["content"][0]["content"][0]["attrs"]["checked"] is True
    assert projected[0]["done"] is True
    assert note.revision == 3
    assert db.commits == 1


def test_note_update_rejects_stale_revision_without_writing():
    note = SimpleNamespace(
        title="Serverstand",
        body_json={"type": "doc", "content": [{"type": "paragraph"}]},
        body_text="",
        is_template=False,
        revision=7,
    )
    db = FakeSession()
    service = NoteService(db, uuid4())
    get_options = []

    def get_note(_note_id, **kwargs):
        get_options.append(kwargs)
        return note

    service._get = get_note

    with pytest.raises(ConflictError) as raised:
        service.update_note(
            uuid4(),
            NoteUpdateRequest(title="Alter Browserstand", base_revision=6),
        )

    assert raised.value.details == {"current_revision": 7}
    assert note.title == "Serverstand"
    assert note.revision == 7
    assert get_options == [{"for_update": True}]
    assert db.commits == 0


def test_nearby_autosaves_are_merged_into_latest_history_entry():
    now = datetime.now(timezone.utc)
    latest = SimpleNamespace(
        reason="autosave",
        note_revision=4,
        title="Vorher",
        body_json={"type": "doc", "content": [{"type": "paragraph"}]},
        body_text="Vorher",
        created_at=now,
        updated_at=now,
    )
    note = SimpleNamespace(
        id=uuid4(),
        revision=5,
        title="Nachher",
        body_json={"type": "doc", "content": [{"type": "paragraph"}]},
        body_text="Nachher",
    )
    db = FakeSession()
    service = NoteService(db, uuid4())
    service._latest_revision = lambda _note_id, **_kwargs: latest

    result = service._record_revision(note, reason="autosave")

    assert result is latest
    assert latest.note_revision == 5
    assert latest.title == "Nachher"
    assert latest.body_text == "Nachher"
    assert not hasattr(db, "added")


def test_ai_change_starts_a_separate_history_entry():
    now = datetime.now(timezone.utc)
    latest = SimpleNamespace(reason="autosave", updated_at=now)
    note = SimpleNamespace(
        id=uuid4(),
        revision=6,
        title="KI-Fassung",
        body_json={"type": "doc", "content": [{"type": "paragraph"}]},
        body_text="KI-Fassung",
    )
    db = FakeSession()
    owner_id = uuid4()
    service = NoteService(db, owner_id)
    service._latest_revision = lambda _note_id, **_kwargs: latest

    result = service._record_revision(note, reason="ai")

    assert result.reason == "ai"
    assert result.note_revision == 6
    assert result.owner_id == owner_id
    assert db.added == [result]

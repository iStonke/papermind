import unittest
import uuid

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.user import User
from app.schemas.notes import NoteCreateRequest, NoteUpdateRequest
from app.services.note_service import NoteService


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT to_regclass('public.note_revision')")
            ).scalar() is not None
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_schema_ready(), "Notiz-Historie nicht migriert oder DB nicht erreichbar.")
class NoteHistoryPersistenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = User(
            username=f"note-history-{uuid.uuid4().hex[:10]}",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.owner_id = self.user.id
        self.service = NoteService(self.db, self.owner_id)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": self.owner_id})
        self.db.commit()
        self.db.close()

    def test_autosaves_are_bundled_and_an_old_state_can_be_restored(self) -> None:
        note = self.service.create_note(NoteCreateRequest(title="Ausgangsstand"))
        initial_revision = self.service.list_revisions(note.id).items[0]

        note = self.service.update_note(
            note.id,
            NoteUpdateRequest(title="Erste Bearbeitung", base_revision=note.revision),
        )
        note = self.service.update_note(
            note.id,
            NoteUpdateRequest(
                body_json={
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}],
                },
                base_revision=note.revision,
            ),
        )

        bundled = self.service.list_revisions(note.id)
        self.assertEqual(bundled.total, 2)
        self.assertEqual(bundled.items[0].note_revision, note.revision)
        self.assertEqual(bundled.items[0].reason, "autosave")

        checkpoint = self.service.checkpoint_revision(note.id, "navigation")
        self.assertEqual(checkpoint.reason, "navigation")

        note = self.service.update_note(
            note.id,
            NoteUpdateRequest(title="Zweite Bearbeitung", base_revision=note.revision),
        )
        self.assertEqual(self.service.list_revisions(note.id).total, 3)

        revision_before_restore = note.revision
        restored = self.service.restore_revision(
            note.id,
            initial_revision.id,
            base_revision=note.revision,
        )

        self.assertEqual(restored.title, "Ausgangsstand")
        self.assertEqual(restored.revision, revision_before_restore + 1)
        history = self.service.list_revisions(note.id)
        self.assertEqual(history.items[0].reason, "restore")
        self.assertIn("before_restore", {item.reason for item in history.items})


if __name__ == "__main__":
    unittest.main()

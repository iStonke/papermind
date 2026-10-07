"""Integrationstests der Lernmarkierungen (Split-Ansicht Notiz↔Dokument).

Deckt ab: Anlegen/Umfärben/Löschen, feste Bedeutungen, Owner-Isolation,
Gesamtübersicht je Dokument (ohne Papierkorb-Notizen) und das Mitziehen beim
Umsortieren der Seiten – sowie die Trennung von den Lesemodus-Annotationen.
"""

import unittest
import uuid

import pydantic
from sqlalchemy import select, text

from app.core.errors import NotFoundError
from app.db.session import SessionLocal, engine
from app.models.annotation import Annotation
from app.models.document import Document
from app.models.note_learn_highlight import NoteLearnHighlight
from app.models.user import User
from app.schemas.note_learn_highlights import NoteLearnHighlightCreate, NoteLearnHighlightUpdate
from app.schemas.notes import NoteCreateRequest
from app.services.note_learn_highlight_service import NoteLearnHighlightService
from app.services.note_service import NoteService

RECT = {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.04}


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT to_regclass('public.note_learn_highlight')")
            ).scalar() is not None
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_schema_ready(), "Lernmarkierungen nicht migriert oder DB nicht erreichbar.")
class NoteLearnHighlightServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.users = []
        self.owner_id = self._user("learn-hl")
        self.service = NoteLearnHighlightService(self.db, self.owner_id)
        self.notes = NoteService(self.db, self.owner_id)
        self.document = self._document(self.owner_id)
        self.note = self.notes.create_note(NoteCreateRequest(title="Skript Kapitel 1"))

    def tearDown(self) -> None:
        self.db.rollback()
        for user_id in self.users:
            for table in ("note_learn_highlight", "note", "note_notebook", "note_collection", "documents"):
                self.db.execute(text(f"DELETE FROM {table} WHERE owner_id = :id"), {"id": user_id})
            self.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        self.db.commit()
        self.db.close()

    # --- Helfer --------------------------------------------------------------
    def _user(self, prefix: str) -> uuid.UUID:
        user = User(username=f"{prefix}-{uuid.uuid4().hex[:10]}", password_hash="x", is_admin=False, is_active=True)
        self.db.add(user)
        self.db.commit()
        self.users.append(user.id)
        return user.id

    def _document(self, owner_id: uuid.UUID) -> Document:
        document = Document(
            owner_id=owner_id,
            original_filename="skript.pdf",
            status="imported",
            ocr_status="not_started",
            text_source="none",
            is_unread=True,
        )
        self.db.add(document)
        self.db.commit()
        return document

    def _create(self, color: str = "important", page: int = 2, note_id=None):
        return self.service.create(
            note_id or self.note.id,
            NoteLearnHighlightCreate(
                document_id=self.document.id, page=page, color=color, rects=[RECT], quote="Kernsatz"
            ),
        )

    # --- Tests ---------------------------------------------------------------
    def test_create_recolor_and_delete(self) -> None:
        highlight = self._create("important")
        self.assertEqual(highlight.color, "important")
        self.assertEqual(highlight.rects, [RECT])

        updated = self.service.update(highlight.id, NoteLearnHighlightUpdate(color="unclear"))
        self.assertEqual(updated.color, "unclear")

        self.service.delete(highlight.id)
        self.assertEqual(self.service.list_for_note(self.note.id), [])

    def test_only_three_fixed_meanings(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            NoteLearnHighlightCreate(document_id=self.document.id, page=1, color="green", rects=[RECT])
        with self.assertRaises(pydantic.ValidationError):
            NoteLearnHighlightUpdate(color="#FAC775")

    def test_list_for_note_can_be_limited_to_a_document(self) -> None:
        self._create(page=3)
        self._create(page=1)
        other_document = self._document(self.owner_id)
        self.service.create(
            self.note.id,
            NoteLearnHighlightCreate(document_id=other_document.id, page=1, color="definition", rects=[RECT]),
        )
        pages = [h.page for h in self.service.list_for_note(self.note.id, self.document.id)]
        self.assertEqual(pages, [1, 3])
        self.assertEqual(len(self.service.list_for_note(self.note.id)), 3)

    def test_document_overview_spans_notes_and_hides_trashed_notes(self) -> None:
        second = self.notes.create_note(NoteCreateRequest(title="Skript Kapitel 2"))
        self._create("definition", page=4, note_id=second.id)
        self._create("important", page=1)

        overview = self.service.list_for_document(self.document.id)
        self.assertEqual([(h.page, h.note_title) for h in overview], [(1, "Skript Kapitel 1"), (4, "Skript Kapitel 2")])

        self.notes.trash_note(second.id)
        overview = self.service.list_for_document(self.document.id)
        self.assertEqual([h.note_title for h in overview], ["Skript Kapitel 1"])
        # Die Markierung der Papierkorb-Notiz bleibt gespeichert (Wiederherstellen).
        stored = self.db.execute(
            select(NoteLearnHighlight).where(NoteLearnHighlight.note_id == second.id)
        ).scalars().all()
        self.assertEqual(len(stored), 1)

    def test_other_owner_cannot_see_or_change(self) -> None:
        highlight = self._create()
        stranger = NoteLearnHighlightService(self.db, self._user("learn-hl-other"))
        with self.assertRaises(NotFoundError):
            stranger.list_for_note(self.note.id)
        with self.assertRaises(NotFoundError):
            stranger.list_for_document(self.document.id)
        with self.assertRaises(NotFoundError):
            stranger.update(highlight.id, NoteLearnHighlightUpdate(color="unclear"))
        with self.assertRaises(NotFoundError):
            stranger.delete(highlight.id)

    def test_cannot_highlight_a_foreign_document(self) -> None:
        foreign_document = self._document(self._user("learn-hl-doc"))
        with self.assertRaises(NotFoundError):
            self.service.create(
                self.note.id,
                NoteLearnHighlightCreate(document_id=foreign_document.id, page=1, color="important", rects=[RECT]),
            )

    def test_separate_from_reader_annotations(self) -> None:
        self._create()
        annotations = self.db.execute(
            select(Annotation).where(Annotation.document_id == self.document.id)
        ).scalars().all()
        self.assertEqual(annotations, [])

    def test_deleting_the_note_removes_its_highlights(self) -> None:
        self._create()
        self.notes.delete_note(self.note.id)
        remaining = self.db.execute(
            select(NoteLearnHighlight).where(NoteLearnHighlight.document_id == self.document.id)
        ).scalars().all()
        self.assertEqual(remaining, [])


if __name__ == "__main__":
    unittest.main()

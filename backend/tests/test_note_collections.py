import unittest
import uuid

from sqlalchemy import text

from app.core.errors import ConflictError
from app.db.session import SessionLocal, engine
from app.models.user import User
from app.schemas.notes import (
    CollectionCreateRequest,
    CollectionUpdateRequest,
    NoteCreateRequest,
    NotebookCreateRequest,
    NoteUpdateRequest,
)
from app.services.note_collection_service import DEFAULT_COLLECTION_NAME, NoteCollectionService
from app.services.note_notebook_service import NoteNotebookService
from app.services.note_service import NoteService


def _schema_ready() -> bool:
    try:
        with engine.connect() as connection:
            return connection.execute(
                text("SELECT to_regclass('public.note_collection')")
            ).scalar() is not None
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_schema_ready(), "Sammlungen nicht migriert oder DB nicht erreichbar.")
class NoteCollectionServiceTest(unittest.TestCase):
    """Integrationstests des Sammlungs-Services gegen die echte DB.

    Deckt die harte Partition ab: Scoping, Notizbuch-Vererbung, Move-mit-
    Abkopplung, Lösch-Wächter und die Vorlagen-Ausnahme (global).
    """

    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = User(
            username=f"note-collections-{uuid.uuid4().hex[:10]}",
            password_hash="x",
            is_admin=False,
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.owner_id = self.user.id
        self.collections = NoteCollectionService(self.db, self.owner_id)
        self.notebooks = NoteNotebookService(self.db, self.owner_id)
        self.notes = NoteService(self.db, self.owner_id)

    def tearDown(self) -> None:
        self.db.rollback()
        # Notizen zuerst löschen, damit die RESTRICT-FK note.collection_id die
        # anschließende Sammlungs-/User-Löschung nicht blockiert.
        for table in ("note", "note_notebook", "note_collection"):
            self.db.execute(
                text(f"DELETE FROM {table} WHERE owner_id = :id"), {"id": self.owner_id}
            )
        self.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": self.owner_id})
        self.db.commit()
        self.db.close()

    # --- Helfer --------------------------------------------------------------
    def _collection(self, name: str, color: str | None = None):
        return self.collections.create_collection(
            CollectionCreateRequest(name=name, color=color)
        )

    def _titles(self, **kwargs) -> list[str]:
        return [item.title for item in self.notes.list_notes(**kwargs)]

    # --- Tests ---------------------------------------------------------------
    def test_list_collections_creates_a_default_lazily(self) -> None:
        result = self.collections.list_collections()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, DEFAULT_COLLECTION_NAME)
        # Idempotent: ein zweiter Aufruf legt keine weitere an.
        self.assertEqual(len(self.collections.list_collections()), 1)

    def test_create_rename_recolor_and_unique_conflict(self) -> None:
        arb = self._collection("Arbeit", color="#111111")
        self.assertEqual(arb.name, "Arbeit")
        self.assertEqual(arb.color, "#111111")

        renamed = self.collections.update_collection(
            arb.id, CollectionUpdateRequest(name="Beruf")
        )
        self.assertEqual(renamed.name, "Beruf")

        # Farbe zurücksetzen (color explizit None).
        cleared = self.collections.update_collection(
            arb.id, CollectionUpdateRequest(color=None)
        )
        self.assertIsNone(cleared.color)

        with self.assertRaises(ConflictError):
            self._collection("Beruf")

    def test_notes_and_notebooks_are_scoped_by_collection(self) -> None:
        default_id = self.collections.ensure_default_id()
        arb = self._collection("Arbeit")

        self.notebooks.create_notebook(
            NotebookCreateRequest(name="Projekt", collection_id=arb.id)
        )
        self.assertEqual([nb.name for nb in self.notebooks.list_notebooks(arb.id)], ["Projekt"])
        self.assertEqual(self.notebooks.list_notebooks(default_id), [])

        self.notes.create_note(NoteCreateRequest(title="A", collection_id=arb.id))
        self.notes.create_note(NoteCreateRequest(title="B", collection_id=default_id))

        self.assertEqual(self._titles(collection_id=arb.id), ["A"])
        default_titles = self._titles(collection_id=default_id)
        self.assertIn("B", default_titles)
        self.assertNotIn("A", default_titles)

    def test_note_in_notebook_inherits_collection(self) -> None:
        default_id = self.collections.ensure_default_id()
        arb = self._collection("Arbeit")
        nb = self.notebooks.create_notebook(
            NotebookCreateRequest(name="Projekt", collection_id=arb.id)
        )

        # Anlegen mit Notizbuch → Sammlung wird vom Notizbuch bestimmt.
        created = self.notes.create_note(NoteCreateRequest(title="X", notebook_id=nb.id))
        self.assertEqual(created.collection_id, arb.id)
        self.assertEqual(created.notebook_id, nb.id)

        # Umhängen in ein Notizbuch der anderen Sammlung zieht die Sammlung mit.
        other = self.notes.create_note(NoteCreateRequest(title="Y", collection_id=default_id))
        self.assertEqual(other.collection_id, default_id)
        moved = self.notes.update_note(other.id, NoteUpdateRequest(notebook_id=nb.id))
        self.assertEqual(moved.collection_id, arb.id)
        self.assertEqual(moved.notebook_id, nb.id)

    def test_move_notes_detaches_notebook(self) -> None:
        default_id = self.collections.ensure_default_id()
        arb = self._collection("Arbeit")
        nb = self.notebooks.create_notebook(
            NotebookCreateRequest(name="Projekt", collection_id=arb.id)
        )
        note = self.notes.create_note(NoteCreateRequest(title="X", notebook_id=nb.id))

        affected = self.collections.move_notes([note.id], default_id)
        self.assertEqual(affected, 1)

        refreshed = self.notes.get_note(note.id)
        self.assertEqual(refreshed.collection_id, default_id)
        self.assertIsNone(refreshed.notebook_id)

    def test_delete_guards_last_and_non_empty(self) -> None:
        default_id = self.collections.ensure_default_id()
        # Letzte Sammlung ist nicht löschbar.
        with self.assertRaises(ConflictError):
            self.collections.delete_collection(default_id)

        arb = self._collection("Arbeit")
        nb = self.notebooks.create_notebook(
            NotebookCreateRequest(name="Projekt", collection_id=arb.id)
        )
        note = self.notes.create_note(NoteCreateRequest(title="X", notebook_id=nb.id))

        # Nicht-leer ohne Ziel: abgelehnt.
        with self.assertRaises(ConflictError):
            self.collections.delete_collection(arb.id)

        # Mit Ziel: Notiz + Notizbuch wandern nach Allgemein, Sammlung verschwindet.
        self.collections.delete_collection(arb.id, reassign_to=default_id)
        names = [c.name for c in self.collections.list_collections()]
        self.assertNotIn("Arbeit", names)
        self.assertEqual(self.notes.get_note(note.id).collection_id, default_id)
        self.assertEqual([n.name for n in self.notebooks.list_notebooks(default_id)], ["Projekt"])

    def test_templates_are_global_and_unscoped(self) -> None:
        arb = self._collection("Arbeit")
        template = self.notes.create_note(
            NoteCreateRequest(title="T", is_template=True, collection_id=arb.id)
        )
        # Vorlage bewusst ohne Sammlung (global).
        self.assertIsNone(template.collection_id)

        # In der (gescopten) regulären Liste taucht sie nicht auf …
        self.assertNotIn("T", self._titles(collection_id=arb.id))
        # … in der Vorlagenliste dagegen schon, trotz mitgegebener Sammlung.
        self.assertIn("T", self._titles(templates=True, collection_id=arb.id))

    def test_reorder_collections_sets_positions(self) -> None:
        self.collections.ensure_default_id()
        a = self._collection("A")
        b = self._collection("B")
        c = self._collection("C")

        ordered = self.collections.reorder_collections([c.id, a.id, b.id])
        self.assertEqual([col.id for col in ordered[:3]], [c.id, a.id, b.id])


if __name__ == "__main__":
    unittest.main()

"""Integrationstest für die DB-seitige Daten-Isolation (Row-Level Security).

Beweist OHNE HTTP-Login, dass die Web-Rolle ``papermind_app`` nur Daten des in
``app.owner_id`` gesetzten Benutzers sieht. Wird übersprungen, wenn keine
separate App-Rolle konfiguriert ist (dann ist RLS unwirksam) oder die DB nicht
erreichbar ist.

Setup/Teardown laufen über die Superuser-Verbindung (umgeht RLS), die
eigentlichen Prüfungen über die App-Rolle.
"""

import unittest
import uuid

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal, app_engine
from app.models.document import Document
from app.models.user import User


def _make_user(db, suffix: str) -> User:
    user = User(
        username=f"rls-test-{suffix}-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        is_admin=False,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_doc(db, owner_id: uuid.UUID) -> Document:
    doc = Document(
        owner_id=owner_id,
        original_filename=f"rls-{uuid.uuid4().hex[:8]}.pdf",
        status="imported",
        ocr_status="not_started",
        text_source="none",
        is_unread=True,
    )
    db.add(doc)
    db.flush()
    return doc


@unittest.skipUnless(
    get_settings().app_database_url,
    "APP_DATABASE_URL nicht gesetzt – RLS ist unwirksam, Test übersprungen.",
)
class RowLevelSecurityIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Erreichbarkeit der App-Rolle prüfen, sonst überspringen.
        try:
            with app_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"App-DB-Rolle nicht erreichbar: {exc}")

        cls.db = SessionLocal()  # Superuser → für Setup/Teardown (umgeht RLS)
        cls.user_a = _make_user(cls.db, "a")
        cls.user_b = _make_user(cls.db, "b")
        cls.db.commit()
        cls.doc_a = _make_doc(cls.db, cls.user_a.id)
        cls.doc_b = _make_doc(cls.db, cls.user_b.id)
        cls.db.commit()
        cls.id_a, cls.id_b = cls.doc_a.id, cls.doc_b.id
        cls.uid_a, cls.uid_b = cls.user_a.id, cls.user_b.id

    @classmethod
    def tearDownClass(cls) -> None:
        # Benutzer löschen → Dokumente fallen per ON DELETE CASCADE weg.
        for uid in (getattr(cls, "uid_a", None), getattr(cls, "uid_b", None)):
            if uid is not None:
                cls.db.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        cls.db.commit()
        cls.db.close()

    def _visible_doc_ids(self, owner_id: uuid.UUID | None) -> set[uuid.UUID]:
        """IDs, die die App-Rolle mit gesetztem app.owner_id sieht."""
        with app_engine.connect() as conn:
            if owner_id is not None:
                conn.execute(
                    text("SELECT set_config('app.owner_id', :o, false)"), {"o": str(owner_id)}
                )
            rows = conn.execute(text("SELECT id FROM documents")).scalars().all()
        return set(rows)

    def test_owner_a_sees_only_own_document(self) -> None:
        visible = self._visible_doc_ids(self.uid_a)
        self.assertIn(self.id_a, visible)
        self.assertNotIn(self.id_b, visible)

    def test_owner_b_sees_only_own_document(self) -> None:
        visible = self._visible_doc_ids(self.uid_b)
        self.assertIn(self.id_b, visible)
        self.assertNotIn(self.id_a, visible)

    def test_without_owner_sees_nothing(self) -> None:
        # Ohne gesetzten Owner blockt RLS alles (fail-closed).
        self.assertEqual(self._visible_doc_ids(None), set())

    def test_superuser_sees_all(self) -> None:
        # Gegenprobe: der Worker-/System-Pfad (Superuser) sieht beide Dokumente.
        rows = set(self.db.execute(text("SELECT id FROM documents")).scalars().all())
        self.assertIn(self.id_a, rows)
        self.assertIn(self.id_b, rows)


if __name__ == "__main__":
    unittest.main()

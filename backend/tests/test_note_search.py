from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services.note_service import NoteService, _search_preview


class CapturingSession:
    def __init__(self, notes=None):
        self.notes = list(notes or [])
        self.statements = []

    def scalars(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: list(self.notes))

    def execute(self, statement):
        # Verweiszählung (link_count) läuft über execute(); im Unit-Test ohne
        # echte note_link-Zeilen genügt ein leeres Aggregat.
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: [])


def note_row(*, body_text: str = "Ein kurzer Notiztext"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        title="Recherche",
        body_text=body_text,
        is_template=False,
        is_deleted=False,
        deleted_at=None,
        notebook_id=None,
        is_favorite=False,
        created_at=now,
        updated_at=now,
    )


def compiled_sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


class NoteSearchTest(unittest.TestCase):
    def test_global_note_search_uses_the_note_full_text_vector(self):
        db = CapturingSession([note_row()])

        items = NoteService(db, uuid4()).list_notes(q="wichtige Fundstelle")

        self.assertEqual(len(items), 1)
        sql = compiled_sql(db.statements[0])
        self.assertIn("note.search_vector @@", sql)
        self.assertTrue("to_tsquery" in sql or "websearch_to_tsquery" in sql)

    def test_global_note_search_also_matches_tags_and_notebook_names(self):
        db = CapturingSession([note_row()])

        NoteService(db, uuid4()).list_notes(q="Steuern")

        sql = compiled_sql(db.statements[0])
        self.assertIn("note_tags", sql)
        self.assertIn("tags", sql)
        self.assertIn("note_notebook", sql)
        self.assertIn("ILIKE", sql)

    def test_note_search_can_be_limited_to_title_or_body(self):
        title_db = CapturingSession()
        body_db = CapturingSession()

        NoteService(title_db, uuid4()).list_notes(q="Angebot", search_scope="title")
        NoteService(body_db, uuid4()).list_notes(q="Angebot", search_scope="body")

        title_sql = compiled_sql(title_db.statements[0])
        body_sql = compiled_sql(body_db.statements[0])
        title_where = title_sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
        body_where = body_sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
        self.assertIn("note.title", title_where)
        self.assertIn("ILIKE", title_where)
        self.assertNotIn("note.body_text", title_where)
        self.assertIn("note.body_text", body_where)
        self.assertIn("ILIKE", body_where)

    def test_search_preview_centers_the_matching_passage(self):
        text = f"{'Vorlauf ' * 35}entscheidende Fundstelle{' Nachlauf' * 35}"

        preview = _search_preview(text, "Fundstelle")

        self.assertIn("Fundstelle", preview)
        self.assertTrue(preview.startswith("…"))
        self.assertTrue(preview.endswith("…"))
        self.assertLessEqual(len(preview), 202)


if __name__ == "__main__":
    unittest.main()

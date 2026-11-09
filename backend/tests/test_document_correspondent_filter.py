import unittest
import uuid

from sqlalchemy import select

from app.models.document import Document
from app.services.document_query_service import DocumentQueryService


class DocumentCorrespondentFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DocumentQueryService(None)

    def _sql(self, correspondent_id: uuid.UUID | None, *, members: bool = False) -> str:
        # select(Document.id) statt select(Document): so taucht "correspondent_id"
        # nur auf, wenn der Filter tatsächlich eine WHERE-Bedingung ergänzt.
        stmt = self.service._apply_filters(
            select(Document.id),
            None,   # tag
            None,   # tag_ids
            False,  # untagged
            None,   # status
            None,   # date_from
            None,   # date_to
            False,  # recent_imports
            in_trash=False,
            favorites_only=False,
            without_text=False,
            document_type=None,
            correspondent_id=correspondent_id,
            attention=None,
            correspondent_members=members,
        )
        return str(stmt)

    def test_correspondent_id_adds_where_clause(self) -> None:
        sql = self._sql(uuid.uuid4())
        self.assertIn("documents.correspondent_id", sql)

    def test_without_correspondent_id_no_clause(self) -> None:
        sql = self._sql(None)
        self.assertNotIn("correspondent_id", sql)

    def test_members_flag_rolls_up_assigned_persons(self) -> None:
        sql = self._sql(uuid.uuid4(), members=True)
        self.assertIn("correspondents.parent_id", sql)
        self.assertIn(" OR ", sql)
        # Zwei Stufen (Sammlung → Organisation → Person): die Mitglieder-
        # Unterabfrage steht direkt und verschachtelt in der Enkel-Abfrage.
        self.assertEqual(sql.count("correspondents.parent_id"), 3)
        self.assertEqual(sql.count("documents.correspondent_id IN"), 2)

    def test_without_members_flag_matches_only_the_correspondent(self) -> None:
        sql = self._sql(uuid.uuid4(), members=False)
        self.assertNotIn("parent_id", sql)

    def test_members_flag_without_correspondent_is_ignored(self) -> None:
        sql = self._sql(None, members=True)
        self.assertNotIn("correspondent_id", sql)


if __name__ == "__main__":
    unittest.main()

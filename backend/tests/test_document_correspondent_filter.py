import unittest
import uuid

from sqlalchemy import select

from app.models.document import Document
from app.services.document_query_service import DocumentQueryService


class DocumentCorrespondentFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DocumentQueryService(None)

    def _sql(self, correspondent_id: uuid.UUID | None) -> str:
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
        )
        return str(stmt)

    def test_correspondent_id_adds_where_clause(self) -> None:
        sql = self._sql(uuid.uuid4())
        self.assertIn("documents.correspondent_id", sql)

    def test_without_correspondent_id_no_clause(self) -> None:
        sql = self._sql(None)
        self.assertNotIn("correspondent_id", sql)


if __name__ == "__main__":
    unittest.main()

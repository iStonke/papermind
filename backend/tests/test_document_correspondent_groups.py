import unittest
import uuid
from unittest.mock import MagicMock

from sqlalchemy import select

from app.models.document import Document
from app.schemas.documents import DocumentSortField, DocumentSearchScope, SortOrder
from app.services.document_query_service import DocumentQueryService
from app.services.smart_folders import SmartFolderService


class DocumentCorrespondentGroupsTest(unittest.TestCase):
    def setUp(self):
        self.owner_id = uuid.uuid4()
        self.db = MagicMock()
        self.query = DocumentQueryService(self.db, self.owner_id)

    def test_counts_use_complete_filtered_owner_selection_without_pagination(self):
        correspondent_id = uuid.uuid4()
        self.db.execute.return_value.all.return_value = [
            (correspondent_id, "Kieler Männer-Turnverein", "KMTV", "organization", 120),
            (None, None, None, None, 3),
        ]
        source = self.query._scope(select(Document)).where(Document.document_type == "Rechnung")
        groups = self.query.correspondent_groups(source)
        self.assertEqual([group.count for group in groups], [120, 3])
        self.assertEqual(groups[0].short_name, "KMTV")
        self.assertEqual(groups[0].kind, "organization")
        self.assertIsNone(groups[1].kind)
        self.assertIsNone(groups[1].correspondent_id)
        stmt = self.db.execute.call_args.args[0]
        sql = str(stmt)
        self.assertIn("documents.owner_id", sql)
        self.assertIn("correspondents.owner_id", sql)
        self.assertIn("documents.document_type", sql)
        self.assertIn("LEFT OUTER JOIN", sql)
        self.assertNotIn("LIMIT", sql)
        self.assertNotIn("OFFSET", sql)
        self.assertNotIn("text_content", sql)

    def test_unassigned_documents_are_filtered_before_pagination_and_group_count(self):
        self.db.execute.return_value.scalars.return_value.unique.return_value.all.return_value = []
        self.db.execute.return_value.all.return_value = []
        self.query.list_documents(
            q=None, tag=None, tag_ids=None, untagged=False, status=None,
            date_from=None, date_to=None, recent_imports=False,
            sort=DocumentSortField.correspondent_date, order=SortOrder.desc,
            limit=50, offset=50, include_total=False,
            without_correspondent=True, include_correspondent_groups=True,
        )
        statements = [str(call.args[0]) for call in self.db.execute.call_args_list]
        self.assertTrue(all("documents.correspondent_id IS NULL" in sql for sql in statements))
        self.assertIn("GROUP BY", statements[0])
        self.assertNotIn("LIMIT", statements[0])
        self.assertIn("documents.document_date DESC NULLS LAST", statements[1])

    def test_smart_folder_group_filter_is_combined_with_folder_and_search(self):
        service = SmartFolderService(self.db, self.owner_id)
        service.get_smart_folder_or_404 = MagicMock(return_value=MagicMock(query_json={}))
        service.compiler.compile = MagicMock(return_value=Document.document_type == "Rechnung")
        service._list_documents = MagicMock()
        service.list_folder_documents(
            uuid.uuid4(), q="Verein", search_scope=DocumentSearchScope.title,
            without_correspondent=True, include_correspondent_groups=True,
        )
        sql = str(service._list_documents.call_args.args[0])
        self.assertIn("documents.document_type", sql)
        self.assertIn("documents.correspondent_id IS NULL", sql)
        self.assertIn("display_name", sql)
        self.assertTrue(service._list_documents.call_args.kwargs["include_correspondent_groups"])


if __name__ == "__main__":
    unittest.main()

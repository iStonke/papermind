import unittest

from app.schemas.documents import DocumentSearchScope, DocumentSortField
from app.services.documents import DocumentService


class DocumentSearchScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DocumentService(None)

    def test_title_scope_searches_display_name_and_filename(self) -> None:
        compiled = self.service._build_scoped_search_filter("Rechnung", DocumentSearchScope.title)
        sql = str(compiled)

        self.assertIn("documents.display_name", sql)
        self.assertIn("documents.original_filename", sql)

    def test_document_type_scope_searches_document_type(self) -> None:
        compiled = self.service._build_scoped_search_filter("Schule", DocumentSearchScope.document_type)

        self.assertIn("documents.document_type", str(compiled))

    def test_correspondent_scope_searches_correspondents(self) -> None:
        compiled = self.service._build_scoped_search_filter("Reventlouschule", DocumentSearchScope.correspondent)
        sql = str(compiled)

        self.assertIn("correspondents", sql)
        self.assertIn("documents.correspondent_id", sql)

    def test_tags_scope_searches_tags(self) -> None:
        compiled = self.service._build_scoped_search_filter("Bildung", DocumentSearchScope.tags)
        sql = str(compiled)

        self.assertIn("document_tags", sql)
        self.assertIn("tags", sql)

    def test_year_scope_searches_document_date_year(self) -> None:
        compiled = self.service._build_scoped_search_filter("2026", DocumentSearchScope.year)
        sql = str(compiled)

        self.assertIn("EXTRACT(year FROM documents.document_date)", sql)

    def test_year_scope_rejects_non_year_query(self) -> None:
        compiled = self.service._build_scoped_search_filter("2026 Rechnung", DocumentSearchScope.year)

        self.assertEqual(str(compiled), "false")

    def test_unread_sort_field_is_supported(self) -> None:
        self.assertEqual(DocumentSortField("is_unread"), DocumentSortField.is_unread)
        self.assertEqual(DocumentSortField("unread"), DocumentSortField.unread)


if __name__ == "__main__":
    unittest.main()

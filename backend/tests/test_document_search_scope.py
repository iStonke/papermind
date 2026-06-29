import unittest

from app.schemas.documents import DocumentSearchScope
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


if __name__ == "__main__":
    unittest.main()

import unittest

from sqlalchemy import select

from app.models.document import Document
from app.schemas.documents import DocumentAttentionFilter
from app.services.documents import DocumentService


class DocumentAttentionFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = DocumentService(None)

    def _sql(self, attention: DocumentAttentionFilter) -> str:
        stmt = self.service._apply_attention_filter(select(Document), attention)
        return str(stmt)

    def test_unread_filters_is_unread(self) -> None:
        self.assertIn("documents.is_unread", self._sql(DocumentAttentionFilter.unread))

    def test_unclassified_filters_ai_status(self) -> None:
        self.assertIn("documents.ai_status IN", self._sql(DocumentAttentionFilter.unclassified))

    def test_ocr_issues_checks_text_source_and_quality(self) -> None:
        sql = self._sql(DocumentAttentionFilter.ocr_issues)
        self.assertIn("documents.text_source", sql)
        self.assertIn("documents.ocr_quality_status", sql)

    def test_retention_due_joins_retention_table(self) -> None:
        sql = self._sql(DocumentAttentionFilter.retention_due)
        self.assertIn("document_retention", sql)
        self.assertIn("retain_until", sql)


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.documents import DocumentUpdateRequest
from app.services.documents import DocumentService


class DocumentMetadataUpdateTest(unittest.TestCase):
    def test_manual_date_update_recalculates_existing_retention(self) -> None:
        document_id = uuid.uuid4()
        document = SimpleNamespace(
            id=document_id,
            document_date=date(2024, 1, 1),
            document_date_source="ocr",
            document_date_confidence=0.9,
            document_date_candidates=[{"date": "2024-01-01"}],
        )
        retention = SimpleNamespace(
            period_years=1,
            retain_until=date(2034, 1, 1),
            updated_at=None,
        )
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = retention
        service = DocumentService(db)
        service.get_document_or_404 = MagicMock(side_effect=[document, document])

        updated = service.update_document(
            document_id,
            DocumentUpdateRequest(document_date=date(2024, 2, 29)),
        )

        self.assertIs(updated, document)
        self.assertEqual(document.document_date, date(2024, 2, 29))
        self.assertEqual(document.document_date_source, "manual")
        self.assertIsNone(document.document_date_confidence)
        self.assertIsNone(document.document_date_candidates)
        self.assertEqual(retention.retain_until, date(2025, 2, 28))
        self.assertIsNotNone(retention.updated_at)
        db.commit.assert_called_once_with()

    def test_clearing_date_clears_existing_retention_deadline(self) -> None:
        document_id = uuid.uuid4()
        document = SimpleNamespace(
            id=document_id,
            document_date=date(2024, 2, 29),
            document_date_source="manual",
            document_date_confidence=None,
            document_date_candidates=None,
        )
        retention = SimpleNamespace(
            period_years=10,
            retain_until=date(2034, 2, 28),
            updated_at=None,
        )
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = retention
        service = DocumentService(db)
        service.get_document_or_404 = MagicMock(side_effect=[document, document])

        service.update_document(
            document_id,
            DocumentUpdateRequest(document_date=None),
        )

        self.assertIsNone(document.document_date)
        self.assertIsNone(retention.retain_until)


if __name__ == "__main__":
    unittest.main()

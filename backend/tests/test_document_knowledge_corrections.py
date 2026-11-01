import unittest
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.schemas.documents import DocumentUpdateRequest
from app.services.ai_classification import apply_ollama_classification
from app.services.document_dates import DocumentDateExtractionResult, apply_ocr_document_date_result
from app.services.document_knowledge import knowledge_value
from app.services.document_wiki import render_document_wiki_entry
from app.services.documents import DocumentService


class KnowledgeCorrectionsTest(unittest.TestCase):
    def test_corrections_survive_reclassification_and_keep_original_evidence(self):
        document = SimpleNamespace(id=uuid.uuid4(), flags={"ocr": {"quality": "good"}}, ai_amount=Decimal("12"), ai_recipient="Alt")
        db = MagicMock()
        service = DocumentService(db)
        service.get_document_or_404 = MagicMock(return_value=document)
        service.update_document(document.id, DocumentUpdateRequest(amount="225.00", currency="EUR", recipient="Korrektur"))
        self.assertEqual(document.amount, Decimal("225.00"))
        self.assertEqual(document.ai_amount, Decimal("12"))
        self.assertEqual(document.flags["manual_metadata_fields"], ["amount", "currency", "recipient"])
        self.assertEqual(document.flags["ocr"], {"quality": "good"})
        result = SimpleNamespace(document_type="Rechnung", document_date=None, sender="Sender", recipient="Neu erkannt",
                                 amount=Decimal("999"), currency="USD", summary="Text", tags=[], confidence=.9, raw_response="{}")
        with patch("app.services.ai_classification.OllamaClassificationService") as classifier:
            classifier.return_value.classify.return_value = result
            warning = apply_ollama_classification(document, extracted_text="Text", quality_status="good", confidence_score=90)
        self.assertIsNone(warning)
        self.assertEqual(document.ai_amount, Decimal("999"))
        self.assertEqual(knowledge_value(document, "amount"), Decimal("225.00"))
        self.assertEqual(knowledge_value(document, "recipient"), "Korrektur")
        self.assertEqual(knowledge_value(document, "currency"), "EUR")

    def test_explicit_clears_are_persisted_and_not_restored_by_ocr_or_ai(self):
        document = SimpleNamespace(id=uuid.uuid4(), flags=None, ai_recipient="Alt", ai_amount=42,
                                   document_date=date(2026, 1, 1), document_date_source="ocr")
        db = MagicMock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        service = DocumentService(db)
        service.get_document_or_404 = MagicMock(return_value=document)
        service.update_document(document.id, DocumentUpdateRequest(recipient=None, amount=None, document_date=None, document_type=None, correspondent_id=None))
        self.assertIsNone(knowledge_value(document, "recipient"))
        self.assertIsNone(knowledge_value(document, "amount"))
        extraction = DocumentDateExtractionResult(best_date=date(2026, 2, 1), best_confidence=.99, candidates=[])
        self.assertFalse(apply_ocr_document_date_result(document, extraction))
        self.assertIsNone(document.document_date)
        document.ai_status = "done"
        document.ai_document_date = date(2026, 2, 1)
        document.ai_summary = "Text"
        with patch.object(service, "_build_ai_title", return_value=None), patch.object(service, "_suggest_tags_from_classification", return_value=[]):
            suggestion = service.suggest_metadata(document.id)
        self.assertIsNone(suggestion.document_type)
        self.assertIsNone(suggestion.document_date)
        self.assertIsNone(suggestion.correspondent_id)

    def test_request_validation_and_normalization(self):
        self.assertEqual(DocumentUpdateRequest(recipient=" Max ", amount="0.00").recipient, "Max")
        for values in ({"amount": "NaN"}, {"amount": "12.345"}, {"amount": "10000000000"}, {"currency": "EURO"}, {"recipient": "x" * 256}):
            with self.assertRaises(ValidationError):
                DocumentUpdateRequest(**values)

    def test_corrected_money_keeps_amount_and_currency_together(self):
        document = SimpleNamespace(id=uuid.uuid4(), flags={}, ai_amount=Decimal("12.50"), ai_currency="EUR")
        service = DocumentService(MagicMock())
        service.get_document_or_404 = MagicMock(return_value=document)
        service.update_document(document.id, DocumentUpdateRequest(amount="225"))
        document.ai_currency = "USD"
        self.assertEqual(knowledge_value(document, "currency"), "EUR")
        self.assertEqual(document.flags["manual_metadata_fields"], ["amount", "currency"])

    def test_chat_working_note_uses_corrected_values(self):
        document = SimpleNamespace(display_name="Beleg", original_filename="beleg.pdf", document_type="Rechnung", ai_document_type=None,
            document_date=None, ai_document_date=None, ai_sender="Sender", ai_summary="", ai_recipient="Alt", ai_amount=999, ai_currency="USD",
            recipient="Neu", amount=Decimal("225"), currency="EUR", flags={})
        content = render_document_wiki_entry(document)
        self.assertIn("225,00 EUR", content)
        self.assertIn("Neu", content)
        self.assertNotIn("999", content)


if __name__ == "__main__":
    unittest.main()

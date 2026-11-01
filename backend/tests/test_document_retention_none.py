import json
import unittest
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.schemas.retention import DocumentRetentionRead, DocumentRetentionUpdateRequest
from app.services.retention import DocumentRetentionService, _compute_retain_until
from app.services.retention_classification import (
    OllamaRetentionInput,
    OllamaRetentionRule,
    build_ollama_retention_payload,
    parse_ollama_retention_response,
)


class NoDocumentRetentionTest(unittest.TestCase):
    def test_none_unknown_and_unlimited_remain_distinct_without_deadlines(self):
        for period in (0, None, -1):
            with self.subTest(period=period):
                request = DocumentRetentionUpdateRequest(period_years=period)
                self.assertEqual(request.model_dump()["period_years"], period)
                self.assertIsNone(_compute_retain_until(date(2026, 6, 15), period))
        self.assertEqual(_compute_retain_until(date(2026, 6, 15), 10), date(2036, 6, 15))
        self.assertEqual(_compute_retain_until(date(2024, 2, 29), 3), date(2027, 2, 28))

    def test_saving_no_retention_preserves_the_independent_original_choice(self):
        document_id = uuid.uuid4()
        record = SimpleNamespace(document_id=document_id, status="manual", period_years=6,
                                 paper_original="keep", reason=None, retain_until=date(2029, 1, 1))
        db = MagicMock()
        service = DocumentRetentionService(db)
        service._get_document = MagicMock(return_value=SimpleNamespace(document_date=date(2023, 1, 1)))
        service._ensure_retention_enabled = MagicMock(return_value={})
        service._get_record = MagicMock(return_value=record)
        result = service.update_retention(document_id, DocumentRetentionUpdateRequest(
            period_years=0, paper_original="keep", reason="Freiwillig behalten"))
        self.assertEqual(record.period_years, 0)
        self.assertIsNone(record.retain_until)
        self.assertEqual(result.paper_original.value, "keep")
        self.assertEqual(result.model_dump(mode="json")["period_years"], 0)
        db.commit.assert_called_once_with()

    def test_old_zero_year_records_do_not_expose_a_misleading_deadline(self):
        result = DocumentRetentionRead(document_id=uuid.uuid4(), period_years=0, retain_until=date(2026, 6, 15))
        self.assertIsNone(result.retain_until)

    def test_ai_output_and_house_rules_preserve_explicit_no_retention(self):
        result = parse_ollama_retention_response(json.dumps({"period_years": 0, "paper_original": "keep"}))
        self.assertEqual(result.period_years, 0)
        self.assertEqual(result.paper_original, "keep")
        payload = build_ollama_retention_payload(OllamaRetentionInput(document_id="synthetic", ocr_text="Test",
            rule=OllamaRetentionRule(paper_original="keep", period_years=0, basis="Testregel")))
        self.assertIn("keine Aufbewahrung nötig", payload["prompt"])
        self.assertNotIn("Frist=0 Jahre", payload["prompt"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import httpx

from app.services.ollama_classification import (
    OllamaClassificationError,
    OllamaClassificationInput,
    OllamaClassificationService,
    build_ollama_classification_payload,
    parse_ollama_classification_response,
)


class OllamaClassificationTest(unittest.TestCase):
    def test_parse_valid_json_response(self) -> None:
        result = parse_ollama_classification_response(
            """
            {
              "document_type": "Rechnung",
              "document_date": "2026-04-30",
              "sender": "Praxis Quitsch",
              "recipient": "Jan Steinke",
              "amount": 150.0,
              "currency": "EUR",
              "summary": "Rechnung für osteopathische Behandlung.",
              "tags": ["Rechnung", "Osteopathie", "Gesundheit"],
              "confidence": 0.86
            }
            """
        )

        self.assertEqual(result.document_type, "Rechnung")
        self.assertEqual(result.document_date.isoformat(), "2026-04-30")
        self.assertEqual(str(result.amount), "150.00")
        self.assertEqual(result.currency, "EUR")
        self.assertEqual(result.tags, ["Rechnung", "Osteopathie", "Gesundheit"])
        self.assertEqual(result.confidence, 0.86)

    def test_parse_missing_key_raises_error(self) -> None:
        with self.assertRaises(OllamaClassificationError):
            parse_ollama_classification_response('{"document_type": "Rechnung"}')

    def test_payload_includes_schema_and_json_mode(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Rechnung Betrag 10 EUR")
        )

        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["stream"])
        self.assertIn("JSON-SCHEMA", payload["prompt"])
        self.assertIn("ausschließlich als", payload["prompt"])

    def test_payload_uses_allowed_document_types(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Gehaltsabrechnung Dezember"),
            allowed_document_types=["Gehaltsabrechnung", "Kontoauszug"],
        )

        self.assertIn("Gehaltsabrechnung|Kontoauszug oder null", payload["prompt"])

    def test_unreachable_ollama_raises_classification_error(self) -> None:
        service = OllamaClassificationService(base_url="http://localhost:11434", timeout_seconds=0.01)
        with patch("app.services.ollama_classification.httpx.post", side_effect=httpx.ConnectError("no route")):
            with self.assertRaises(OllamaClassificationError):
                service.classify(OllamaClassificationInput(document_id="doc-1", ocr_text="Text"))


if __name__ == "__main__":
    unittest.main()

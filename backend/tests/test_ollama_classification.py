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

    def _full_response(self, document_type: str) -> str:
        return (
            "{"
            f'"document_type": "{document_type}",'
            '"document_date": null,'
            '"sender": null,'
            '"recipient": null,'
            '"amount": null,'
            '"currency": null,'
            '"summary": null,'
            '"tags": [],'
            '"confidence": 0.5'
            "}"
        )

    def test_parse_snaps_document_type_to_canonical_casing(self) -> None:
        result = parse_ollama_classification_response(
            self._full_response("gehaltsabrechnung"),
            allowed_document_types=["Gehaltsabrechnung", "Rechnung", "Sonstiges"],
        )

        self.assertEqual(result.document_type, "Gehaltsabrechnung")

    def test_parse_maps_unknown_type_to_sonstiges(self) -> None:
        result = parse_ollama_classification_response(
            self._full_response("Lieferschein-Sonderfall"),
            allowed_document_types=["Rechnung", "Sonstiges"],
        )

        self.assertEqual(result.document_type, "Sonstiges")

    def test_parse_keeps_unknown_type_when_no_sonstiges_allowed(self) -> None:
        result = parse_ollama_classification_response(
            self._full_response("Sonderbescheid"),
            allowed_document_types=["Rechnung", "Brief"],
        )

        self.assertEqual(result.document_type, "Sonderbescheid")

    def test_parse_without_allowed_list_keeps_raw_type(self) -> None:
        result = parse_ollama_classification_response(self._full_response("eigenwilliger typ"))

        self.assertEqual(result.document_type, "eigenwilliger typ")

    def test_payload_includes_schema_and_json_mode(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Rechnung Betrag 10 EUR")
        )

        self.assertEqual(payload["format"], "json")
        self.assertFalse(payload["stream"])
        # keep_alive hält das Modell resident, sonst Reload-Kosten pro Call.
        self.assertTrue(str(payload["keep_alive"]))
        self.assertIn("JSON-SCHEMA", payload["prompt"])
        self.assertIn("ausschließlich als", payload["prompt"])

    def test_payload_uses_allowed_document_types(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Gehaltsabrechnung Dezember"),
            allowed_document_types=["Gehaltsabrechnung", "Kontoauszug"],
        )

        self.assertIn("Gehaltsabrechnung|Kontoauszug oder null", payload["prompt"])

    def test_payload_includes_document_type_hints(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Gehaltsabrechnung Dezember"),
            allowed_document_types=["Gehaltsabrechnung", "Rechnung"],
            document_type_hints={"Gehaltsabrechnung": "Monatliche Lohn-/Gehaltsmitteilung des Arbeitgebers."},
        )

        self.assertIn("TYP-HINWEISE", payload["prompt"])
        self.assertIn("Gehaltsabrechnung: Monatliche Lohn-/Gehaltsmitteilung", payload["prompt"])

    def test_payload_without_hints_has_no_hint_block(self) -> None:
        payload = build_ollama_classification_payload(
            OllamaClassificationInput(document_id="doc-1", ocr_text="Rechnung"),
            allowed_document_types=["Rechnung"],
        )

        self.assertNotIn("TYP-HINWEISE", payload["prompt"])

    def test_unreachable_ollama_raises_classification_error(self) -> None:
        service = OllamaClassificationService(base_url="http://localhost:11434", timeout_seconds=0.01)
        with patch("app.services.ollama_classification.httpx.post", side_effect=httpx.ConnectError("no route")):
            with self.assertRaises(OllamaClassificationError):
                service.classify(OllamaClassificationInput(document_id="doc-1", ocr_text="Text"))


if __name__ == "__main__":
    unittest.main()

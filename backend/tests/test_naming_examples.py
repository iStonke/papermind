import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.import_staging import ImportStagingService


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class NamingExamplesBlockTest(unittest.TestCase):
    def test_empty_returns_blank(self) -> None:
        self.assertEqual(ImportStagingService._build_naming_examples_block(None), "")
        self.assertEqual(ImportStagingService._build_naming_examples_block([]), "")
        self.assertEqual(ImportStagingService._build_naming_examples_block(["", "   "]), "")

    def test_contains_names_and_subject_guidance(self) -> None:
        block = ImportStagingService._build_naming_examples_block(
            ["Rechnung – Vodafone – Mobilfunk – 11.2024"]
        )
        self.assertIn("Rechnung – Vodafone – Mobilfunk – 11.2024", block)
        self.assertIn("subject", block)
        # Stil-, nicht Wörtlich-Hinweis
        self.assertIn("NICHT wörtlich", block)

    def test_caps_to_three_examples(self) -> None:
        block = ImportStagingService._build_naming_examples_block(
            ["Eins", "Zwei", "Drei", "Vier", "Fünf"]
        )
        self.assertIn("- Eins", block)
        self.assertIn("- Drei", block)
        self.assertNotIn("- Vier", block)
        example_lines = [line for line in block.splitlines() if line.startswith("- ")]
        self.assertEqual(len(example_lines), 3)

    def test_dedupes_case_insensitively(self) -> None:
        block = ImportStagingService._build_naming_examples_block(
            ["Rechnung Vodafone", "rechnung vodafone", "Mahnung HUK"]
        )
        self.assertEqual(block.lower().count("rechnung vodafone"), 1)
        self.assertIn("Mahnung HUK", block)

    def test_strips_pdf_suffix_and_truncates(self) -> None:
        long_name = "A" * 200 + ".pdf"
        block = ImportStagingService._build_naming_examples_block([long_name], max_len=80)
        self.assertNotIn(".pdf", block)
        # längste Beispielzeile darf max_len nicht überschreiten (+ "- " Präfix)
        longest = max((line for line in block.splitlines() if line.startswith("- ")), key=len)
        self.assertLessEqual(len(longest) - 2, 80)


class CallOllamaStagingTest(unittest.TestCase):
    """Regression: _call_ollama_for_staging ist @staticmethod; verschachtelte
    Helfer dürfen kein `self` referenzieren. Prüft zugleich, dass der Few-Shot-
    Block in den Prompt gelangt und die Antwort sauber geparst wird."""

    _LLM_JSON = (
        '{"doc_type":"Rechnung","issuer":"Vodafone","subject":"Mobilfunk",'
        '"date":"2024-11-01","tags":["Mobilfunk"],"amount":12.5,'
        '"currency":"EUR","summary":"Kurzfakten"}'
    )

    def test_parses_response_and_includes_examples(self) -> None:
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["prompt"] = json["prompt"]
            return _FakeResponse({"response": self._LLM_JSON})

        with patch("app.services.import_staging.httpx.post", side_effect=fake_post):
            result = ImportStagingService._call_ollama_for_staging(
                "Rechnung Vodafone Betrag 12,50 EUR",
                base_url="http://localhost:11434",
                model="llama3.2:3b",
                timeout_seconds=5.0,
                max_input_chars=800,
                existing_tags=["Mobilfunk"],
                allowed_doc_types=["Rechnung", "Mahnung"],
                naming_examples=["Rechnung – Vodafone – Mobilfunk – 10.2024"],
            )

        # Kein NameError -> Dict zurück, Felder korrekt geparst
        self.assertIsNotNone(result)
        self.assertEqual(result["doc_type"], "Rechnung")
        self.assertEqual(result["issuer"], "Vodafone")
        self.assertEqual(result["amount"], 12.5)
        self.assertEqual(result["currency"], "EUR")
        # Few-Shot-Block ist im Prompt
        self.assertIn("BEISPIELE", captured["prompt"])
        self.assertIn("Rechnung – Vodafone – Mobilfunk – 10.2024", captured["prompt"])

    def test_accepts_note_alias_for_summary(self) -> None:
        def fake_post(url, json=None, timeout=None):
            return _FakeResponse(
                {
                    "response": (
                        '{"doc_type":"Bescheid","issuer":"Finanzamt","subject":"Einkommensteuer",'
                        '"date":"2025-05-10","tags":["Steuer"],"amount":null,'
                        '"currency":null,"note":"Festsetzung der Einkommensteuer 2024."}'
                    )
                }
            )

        with patch("app.services.import_staging.httpx.post", side_effect=fake_post):
            result = ImportStagingService._call_ollama_for_staging(
                "Einkommensteuerbescheid Finanzamt",
                base_url="http://localhost:11434",
                model="llama3.2:3b",
                timeout_seconds=5.0,
                max_input_chars=800,
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["summary"], "Festsetzung der Einkommensteuer 2024.")

    def test_no_examples_no_block(self) -> None:
        def fake_post(url, json=None, timeout=None):
            self.assertNotIn("BEISPIELE", json["prompt"])
            return _FakeResponse({"response": self._LLM_JSON})

        with patch("app.services.import_staging.httpx.post", side_effect=fake_post):
            result = ImportStagingService._call_ollama_for_staging(
                "Rechnung",
                base_url="http://localhost:11434",
                model="llama3.2:3b",
                timeout_seconds=5.0,
                max_input_chars=800,
                naming_examples=None,
            )
        self.assertIsNotNone(result)


class DefaultTitleDetectionTest(unittest.TestCase):
    def test_default_and_scan_titles(self) -> None:
        for value in ["", "   ", "Scan", "Scan - 03-2024", "Dokument", "Neues Dokument", "Unbenannt"]:
            self.assertTrue(ImportStagingService._looks_like_default_title(value), value)

    def test_real_titles_are_kept(self) -> None:
        for value in ["Rechnung – Vodafone – 11.2024", "Einkommensteuerbescheid 2024", "Mahnung HUK"]:
            self.assertFalse(ImportStagingService._looks_like_default_title(value), value)


class MetadataNoteFallbackTest(unittest.TestCase):
    def test_builds_note_from_detected_metadata(self) -> None:
        note = ImportStagingService._build_note_from_metadata(
            issuer="Vodafone",
            subject="Mobilfunkrechnung",
            doc_type="Rechnung",
            date_iso="2024-11-01",
            amount=12.5,
            currency="EUR",
        )

        self.assertEqual(
            note,
            "Absender: Vodafone. Thema: Mobilfunkrechnung. Dokumenttyp: Rechnung. Datum: 01.11.2024. Betrag: 12,50€",
        )

    def test_returns_none_without_useful_facts(self) -> None:
        self.assertIsNone(
            ImportStagingService._build_note_from_metadata(
                issuer="Unbekannt",
                subject=None,
                doc_type="Sonstiges",
                date_iso=None,
                amount=None,
                currency=None,
            )
        )

    def test_suggest_stage_title_uses_note_fallback_without_error(self) -> None:
        service = ImportStagingService(db=None)
        service.settings_service = SimpleNamespace(
            get_settings=lambda: SimpleNamespace(model_dump=lambda mode="json": {"ollama": {"enabled": False}})
        )

        with (
            patch.object(
                service,
                "_extract_text_for_title_suggestion",
                return_value=(
                    "Rechnung Vodafone Mobilfunk Rechnung vom 01.11.2024 Gesamtbetrag 12,50 EUR " * 2,
                    1,
                    ["source.pdf:1"],
                ),
            ),
            patch.object(service, "_load_existing_tag_names", return_value=[]),
            patch.object(
                service,
                "_extract_rich_metadata",
                return_value={
                    "doc_type": "Rechnung",
                    "issuer": "Vodafone",
                    "subject": "Mobilfunkrechnung",
                    "date": "2024-11-01",
                    "tags": [],
                    "amount": 12.5,
                    "currency": "EUR",
                    "summary": None,
                },
            ),
            patch("app.services.import_staging.load_active_document_type_vocab", return_value=[]),
            patch.object(service, "_resolve_correspondent", return_value=None),
        ):
            result = service.suggest_stage_title(["source-1"], stage_id="stage-1")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            result["meta"]["note"],
            "Absender: Vodafone. Thema: Mobilfunkrechnung. Dokumenttyp: Rechnung. Datum: 01.11.2024. Betrag: 12,50€",
        )


if __name__ == "__main__":
    unittest.main()

import unittest
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


if __name__ == "__main__":
    unittest.main()

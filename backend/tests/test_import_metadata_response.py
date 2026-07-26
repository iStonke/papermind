import unittest

from app.services.import_metadata_response import (
    extract_json_object,
    extract_loose_fields,
    safe_float,
)


class ImportMetadataResponseTest(unittest.TestCase):
    def test_extracts_json_wrapped_in_model_explanation(self) -> None:
        self.assertEqual(
            extract_json_object('Antwort: {"issuer":"Muster GmbH","amount":12.5} Ende'),
            {"issuer": "Muster GmbH", "amount": 12.5},
        )

    def test_extracts_loose_labelled_fields(self) -> None:
        self.assertEqual(
            extract_loose_fields("Firma: Muster GmbH\nBetrag: 12,50\nunklar"),
            {"issuer": "Muster GmbH", "amount": "12,50"},
        )

    def test_safe_float_rejects_non_numeric_value(self) -> None:
        self.assertEqual(safe_float("12,50"), 12.5)
        self.assertIsNone(safe_float("unbekannt"))


if __name__ == "__main__":
    unittest.main()

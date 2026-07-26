import unittest

from app.services.import_metadata_rules import (
    detect_amount_currency,
    detect_document_type,
    detect_document_type_improved,
    extract_document_date,
    normalize_document_type,
)


class ImportMetadataRulesTest(unittest.TestCase):
    def test_detects_invoice_and_prioritizes_total_amount(self) -> None:
        text = "Rechnung Nr. 42\nZwischensumme 9,99 EUR\nGesamtbetrag 12,50 EUR"

        self.assertEqual(detect_document_type(text), "Rechnung")
        self.assertEqual(detect_amount_currency(text), (12.5, "EUR"))

    def test_date_with_context_wins_over_earlier_date(self) -> None:
        text = "Eingang 01.01.2026\nRechnungsdatum: 15.12.2025"

        self.assertEqual(extract_document_date(text), "2025-12-15")

    def test_normalization_preserves_active_vocabulary_casing(self) -> None:
        self.assertEqual(
            normalize_document_type("rechnung", ["RECHNUNG", "Vertrag"]),
            "RECHNUNG",
        )

    def test_invalid_or_non_positive_amount_is_not_returned(self) -> None:
        self.assertEqual(detect_amount_currency("Gesamtbetrag 0,00 EUR"), (None, None))

    def test_improved_type_detection_does_not_misread_abrechnung(self) -> None:
        self.assertEqual(detect_document_type_improved("Jahresabrechnung Strom"), "Sonstiges")
        self.assertEqual(detect_document_type_improved("Einkommensteuerbescheid 2025"), "Bescheid")


if __name__ == "__main__":
    unittest.main()

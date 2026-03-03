import unittest
from datetime import date
from types import SimpleNamespace

from app.services.document_dates import apply_ocr_document_date_result, extract_document_date_candidates


class DocumentDateExtractionTest(unittest.TestCase):
    def test_prefers_labeled_invoice_date_over_due_or_vehicle_dates(self) -> None:
        page_texts = [
            (
                1,
                "\n".join(
                    [
                        "Rechnungsdatum: 15.01.2026",
                        "Zahlbar bis: 30.01.2026",
                        "Erstzulassung: 01.02.2019",
                    ]
                ),
            )
        ]

        result = extract_document_date_candidates(page_texts)

        self.assertEqual(result.best_date, date(2026, 1, 15))
        self.assertAlmostEqual(result.best_confidence or 0.0, 0.9, places=2)
        self.assertGreaterEqual(len(result.candidates), 3)

    def test_apply_ocr_result_keeps_manual_date_by_default(self) -> None:
        result = extract_document_date_candidates([(1, "Rechnungsdatum: 04.03.2026")])
        document = SimpleNamespace(
            document_date=date(2026, 2, 1),
            document_date_source="manual",
            document_date_confidence=None,
            document_date_candidates=None,
        )

        changed = apply_ocr_document_date_result(document, result, overwrite_manual=False)

        self.assertFalse(changed)
        self.assertEqual(document.document_date, date(2026, 2, 1))
        self.assertEqual(document.document_date_source, "manual")
        self.assertIsNone(document.document_date_confidence)
        self.assertIsNotNone(document.document_date_candidates)

    def test_apply_ocr_result_sets_date_when_no_manual_value(self) -> None:
        result = extract_document_date_candidates([(1, "Rechnungsdatum: 04.03.2026")])
        document = SimpleNamespace(
            document_date=None,
            document_date_source="manual",
            document_date_confidence=None,
            document_date_candidates=None,
        )

        changed = apply_ocr_document_date_result(document, result, overwrite_manual=False)

        self.assertTrue(changed)
        self.assertEqual(document.document_date, date(2026, 3, 4))
        self.assertEqual(document.document_date_source, "ocr")
        self.assertAlmostEqual(document.document_date_confidence or 0.0, 0.9, places=2)


if __name__ == "__main__":
    unittest.main()

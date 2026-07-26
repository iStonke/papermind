import unittest

from app.services.import_title_formatting import build_note_from_metadata, sanitize_title


class ImportTitleFormattingTest(unittest.TestCase):
    def test_sanitize_title_removes_filename_characters_and_clips(self) -> None:
        result = sanitize_title('  Rechnung: Strom / Juli 2026?  ', max_len=20)

        self.assertEqual(result, "Rechnung Strom Juli")

    def test_note_contains_only_available_meaningful_metadata(self) -> None:
        result = build_note_from_metadata(
            issuer="Unbekannt",
            subject="Mobilfunk",
            doc_type="Rechnung",
            date_iso="2026-07-26",
            amount=12.5,
            currency="EUR",
        )

        self.assertEqual(result, "Thema: Mobilfunk. Dokumenttyp: Rechnung. Datum: 26.07.2026. Betrag: 12,50€")

    def test_invalid_date_is_not_added_to_note(self) -> None:
        result = build_note_from_metadata(
            issuer=None,
            subject=None,
            doc_type="Sonstiges",
            date_iso="2026-99-99",
            amount=None,
            currency=None,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

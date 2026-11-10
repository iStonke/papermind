import unittest

from app.services.import_metadata_heuristics import (
    detect_sender,
    detect_subject_heuristic,
    extract_issuer_from_line,
    extract_subject_rich,
    is_plausible_sender,
    generate_tags_from_text,
    is_subject_supported_by_context,
    normalize_subject,
)


class ImportMetadataHeuristicsTest(unittest.TestCase):
    def test_sender_detection_prefers_company_line(self) -> None:
        text = "Muster Versicherung GmbH\nKundenservice\nRechnung vom 12.07.2026"

        self.assertEqual(detect_sender(text), "Muster Versicherung")

    def test_short_inspection_labels_do_not_match_word_endings(self):
        self.assertEqual(detect_subject_heuristic('Beim Aufbau helfen'), '')
        self.assertEqual(detect_subject_heuristic('AU bestanden'), 'Hauptuntersuchung')

    def test_free_note_headings_are_not_senders(self):
        self.assertIsNone(detect_sender('Notizen\nTreffen am Gartentor\nMaterial für den Aufbau besorgen.'))

    def test_headings_of_notes_are_not_plausible_senders(self) -> None:
        self.assertFalse(is_plausible_sender("Pi Sync & Betrieb (Merkhilfe)"))
        self.assertFalse(is_plausible_sender("Git-Befehle Übersicht"))
        notes = "Pi Sync und Betrieb\nrsync -av ./ pi:/srv\nDanach Dienst neu starten."
        self.assertFalse(is_plausible_sender("Pi Sync und Betrieb", notes))
        self.assertFalse(is_plausible_sender("", notes))

    def test_placeholder_values_are_not_plausible_senders(self) -> None:
        for placeholder in ("null", "None", "n/a", "Unbekannt", " undefined "):
            self.assertFalse(is_plausible_sender(placeholder), placeholder)

    def test_real_senders_stay_plausible(self) -> None:
        letter = "Stadtwerke Kiel\nPostfach 1234\n24103 Kiel\nSehr geehrte Frau Muster,"
        self.assertTrue(is_plausible_sender("Stadtwerke Kiel", letter))
        self.assertTrue(is_plausible_sender("Notizblock Manufaktur GmbH", "Notizblock Manufaktur GmbH\nIhre Bestellung"))
        self.assertTrue(is_plausible_sender("Vodafone", "Ihre Rechnung\nVodafone"))
        self.assertTrue(is_plausible_sender("Wiker-Auto-Service"))

    def test_issuer_line_collapses_duplicate_ocr_tokens(self) -> None:
        self.assertEqual(extract_issuer_from_line("Vodafone Vodafone, Kundenservice"), "Vodafone")

    def test_subject_normalization_removes_invoice_number_tail(self) -> None:
        self.assertEqual(normalize_subject("Mobilfunk - Rechnungsnummer 42-XY"), "Mobilfunk")

    def test_subject_context_requires_evidence_for_known_labels(self) -> None:
        self.assertEqual(detect_subject_heuristic("Ihre Versicherungspolice"), "Versicherung")
        self.assertTrue(is_subject_supported_by_context("Versicherung", "Ihre Versicherungspolice"))
        self.assertFalse(is_subject_supported_by_context("Energie", "Ihre Versicherungspolice"))

    def test_rich_subject_and_tags_handle_tax_notice(self) -> None:
        text = "Bescheid über Einkommensteuer für 2025 vom Finanzamt"

        self.assertEqual(extract_subject_rich(text, "Bescheid"), "Einkommensteuer 2025")
        self.assertEqual(generate_tags_from_text(text, "Bescheid"), ["Einkommensteuer", "Steuer"])


if __name__ == "__main__":
    unittest.main()

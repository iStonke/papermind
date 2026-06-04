import unicodedata
import unittest
import uuid

from app.services.backlog_import import parse_backlog_csv
from app.services.correspondent_matching import CorrespondentCandidate, match_correspondent


class ParseBacklogCsvTest(unittest.TestCase):
    def test_skips_header_and_splits_tags(self) -> None:
        content = "Dateiname,Tags\n" 'Rechnung.pdf,"Gesundheit, Krankenkasse"\n' "Brief.pdf,Vodafone\n"
        rows = parse_backlog_csv(content)
        self.assertEqual(rows[0], ("Rechnung.pdf", ["Gesundheit", "Krankenkasse"]))
        self.assertEqual(rows[1], ("Brief.pdf", ["Vodafone"]))

    def test_empty_tags_and_dedup(self) -> None:
        content = "Dateiname,Tags\nA.pdf,\nB.pdf,\"HUK, HUK\"\n"
        rows = parse_backlog_csv(content)
        self.assertEqual(rows[0], ("A.pdf", []))
        self.assertEqual(rows[1], ("B.pdf", ["HUK"]))  # case-insensitive dedup

    def test_blank_lines_skipped(self) -> None:
        content = "Dateiname,Tags\n\nA.pdf,X\n"
        rows = parse_backlog_csv(content)
        self.assertEqual(rows, [("A.pdf", ["X"])])


class NfcMatchingTest(unittest.TestCase):
    def test_decomposed_umlaut_matches_precomposed_correspondent(self) -> None:
        # DB-Name zusammengesetzt (NFC), Eingabe zerlegt (NFD, wie von macOS).
        cid = uuid.uuid4()
        candidates = [
            CorrespondentCandidate(correspondent_id=cid, name="Timm-Kröger-Realschule", short_name="TKR")
        ]
        nfd_sender = unicodedata.normalize("NFD", "Timm-Kröger-Realschule")
        self.assertNotEqual(nfd_sender, "Timm-Kröger-Realschule")  # wirklich zerlegt

        match = match_correspondent(candidates, sender=nfd_sender)
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, cid)


if __name__ == "__main__":
    unittest.main()

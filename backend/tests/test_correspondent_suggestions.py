"""Vorschläge für offene Dokumente: vorhandene Korrespondenten zuerst."""
import unittest
import uuid

from app.services.correspondent_matching import CorrespondentCandidate
from app.services.correspondent_suggestions import clean_sender, suggest_from_text


def candidate(name: str, kind: str | None = "organization", **extra) -> CorrespondentCandidate:
    return CorrespondentCandidate(correspondent_id=uuid.uuid4(), name=name, kind=kind, **extra)


class CleanSenderTest(unittest.TestCase):
    def test_phone_address_and_web_are_removed(self) -> None:
        self.assertEqual(clean_sender("Dr. med. Andrea, 04317/333111"), "Dr. med. Andrea")
        self.assertEqual(clean_sender("Plön Regionales Berufsbildungszentrum Tel. 04522 7480 0"), "Plön Regionales Berufsbildungszentrum")
        self.assertEqual(clean_sender("Muster GmbH, info@muster.de"), "Muster GmbH")

    def test_the_part_with_a_legal_form_wins(self) -> None:
        self.assertEqual(
            clean_sender("Leiterin Personalentwicklung, coop eG Benzstraße 10 24148 Kiel www.alles.coop"),
            "coop eG",
        )

    def test_plain_senders_stay_unchanged(self) -> None:
        self.assertEqual(clean_sender("Autohaus Rehder GmbH & Co.KG"), "Autohaus Rehder GmbH & Co.KG")
        self.assertEqual(clean_sender("Hotel Börgerhof, Inh. Marek Burdynowski"), "Hotel Börgerhof, Inh. Marek Burdynowski")
        self.assertEqual(clean_sender(""), "")


class SuggestFromTextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.peters = candidate("Praxis Fr. Peters")
        self.owner = candidate("Jan Steinke", kind="person")
        self.hotel = candidate("Hotel Bürgerhof")
        self.city = candidate("LH Kiel", kind=None)
        self.collection = candidate("Arzt", kind="collection")
        self.pool = [self.peters, self.owner, self.hotel, self.city, self.collection]

    def test_surname_after_title_finds_the_existing_practice(self) -> None:
        text = "Jan Steinke\nMusterweg 1\n24103 Kiel\nPrivatrezept\nDr. med. Andrea Peters\nFachärztin"
        found, similar = suggest_from_text(self.pool, text=text, sender="Dr. med. Andrea", owner_names=("Jan Steinke",))
        self.assertEqual((found.name, found.matched_by), ("Praxis Fr. Peters", "surname"))
        self.assertEqual(similar, [])

    def test_the_recipient_is_never_suggested(self) -> None:
        found, _ = suggest_from_text(self.pool, text="Herrn Jan Steinke\nIhre Rechnung", owner_names=("Jan Steinke",))
        self.assertIsNone(found)

    def test_full_names_in_the_text_win_and_ambiguity_only_hints(self) -> None:
        found, _ = suggest_from_text(self.pool, text="Ihr Aufenthalt im Hotel Bürgerhof")
        self.assertEqual((found.name, found.matched_by), ("Hotel Bürgerhof", "text"))
        other = candidate("Hotel Bürgerhof Kiel")
        found, similar = suggest_from_text([*self.pool, candidate("Bürgerhof")], text="Hotel Bürgerhof")
        self.assertIsNone(found)
        self.assertEqual([entry.name for entry in similar], ["Bürgerhof", "Hotel Bürgerhof"])
        self.assertNotIn(other.name, [entry.name for entry in similar])

    def test_lowercase_words_or_collections_do_not_match(self) -> None:
        found, similar = suggest_from_text(self.pool, text="wir peters und Söhne, arzt", sender="")
        self.assertIsNone(found)
        self.assertEqual(similar, [])

    def test_similar_names_to_the_sender_are_offered_as_hints(self) -> None:
        found, similar = suggest_from_text(self.pool, text="Rechnung", sender="Hotel Börgerhof, Inh. Marek Burdynowski")
        self.assertIsNone(found)
        self.assertEqual([entry.name for entry in similar], ["Hotel Bürgerhof"])
        _, similar = suggest_from_text([candidate("Autohaus Müller KG")], text="", sender="Autohaus Mueller Service")
        self.assertEqual([entry.name for entry in similar], ["Autohaus Müller KG"])

    def test_same_name_except_umlaut_spelling_and_legal_form_is_suggested(self) -> None:
        found, _ = suggest_from_text([candidate("Autohaus Müller")], text="", sender="Autohaus Mueller GmbH")
        self.assertEqual((found.name, found.matched_by), ("Autohaus Müller", "name"))


if __name__ == "__main__":
    unittest.main()

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

    def test_surname_next_to_the_senders_first_name_in_any_order(self) -> None:
        # Praxisstempel: OCR liest „De mee“ statt „Dr. med.“, Nachname vor Vorname.
        text = "Privatrezept\n19.07.25 De mee\nPeters\nAndrea\nAllgemeinmedizin\nHaltenau 12"
        found, _ = suggest_from_text(self.pool, text=text, sender="Dr. med. Andrea", owner_names=("Jan Steinke",))
        self.assertEqual((found.name, found.matched_by), ("Praxis Fr. Peters", "surname"))
        found, _ = suggest_from_text(self.pool, text="Peters\nAllgemeinmedizin", sender="Dr. med. Birgit")
        self.assertIsNone(found)

    def test_the_recipient_is_never_suggested(self) -> None:
        found, _ = suggest_from_text(self.pool, text="Herrn Jan Steinke\nIhre Rechnung", owner_names=("Jan Steinke",))
        self.assertIsNone(found)

    def test_full_names_in_the_text_win_and_ties_pick_the_best(self) -> None:
        found, _ = suggest_from_text(self.pool, text="Ihr Aufenthalt im Hotel Bürgerhof")
        self.assertEqual((found.name, found.matched_by), ("Hotel Bürgerhof", "text"))
        other = candidate("Hotel Bürgerhof Kiel")
        pool = [*self.pool, candidate("Bürgerhof"), other]
        # Mehrere Treffer: der spezifischere wird Vorschlag, der andere Alternative.
        found, similar = suggest_from_text(pool, text="Hotel Bürgerhof")
        self.assertEqual((found.name, found.matched_by), ("Hotel Bürgerhof", "text"))
        self.assertEqual([entry.name for entry in similar], ["Bürgerhof"])
        # Der dem Absender ähnlichere gewinnt vor dem längeren Namen.
        found, similar = suggest_from_text(pool[:-1] + [candidate("Bürgerhof Gastro")], text="Hotel Bürgerhof · Bürgerhof", sender="Bürgerhof Gastro")
        self.assertEqual(found.name, "Bürgerhof Gastro")

    def test_lowercase_words_or_collections_do_not_match(self) -> None:
        found, similar = suggest_from_text(self.pool, text="wir peters und Söhne, arzt", sender="")
        self.assertIsNone(found)
        self.assertEqual(similar, [])

    def test_the_most_similar_existing_name_becomes_the_suggestion(self) -> None:
        found, similar = suggest_from_text(self.pool, text="Rechnung", sender="Hotel Börgerhof, Inh. Marek Burdynowski")
        self.assertEqual((found.name, found.matched_by), ("Hotel Bürgerhof", "similar"))
        self.assertEqual(similar, [])
        found, _ = suggest_from_text([candidate("Autohaus Müller KG")], text="", sender="Autohaus Mueller Service")
        self.assertEqual((found.name, found.matched_by), ("Autohaus Müller KG", "similar"))
        # Weitere ähnliche Namen bleiben als Alternativen, der beste Treffer zuerst.
        pool = [candidate("Stadtwerke Plön"), candidate("Stadtwerke Kiel Netz"), candidate("Kieler Stadtwerke")]
        found, similar = suggest_from_text(pool, text="", sender="Stadtwerke Netz Kiel GmbH")
        self.assertEqual(found.name, "Stadtwerke Kiel Netz")
        self.assertEqual({entry.name for entry in similar}, {"Stadtwerke Plön", "Kieler Stadtwerke"})

    def test_same_name_except_umlaut_spelling_and_legal_form_is_suggested(self) -> None:
        found, _ = suggest_from_text([candidate("Autohaus Müller")], text="", sender="Autohaus Mueller GmbH")
        self.assertEqual((found.name, found.matched_by), ("Autohaus Müller", "name"))


if __name__ == "__main__":
    unittest.main()

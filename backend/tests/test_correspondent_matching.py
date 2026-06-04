import unittest
import uuid

from app.services.correspondent_matching import (
    CorrespondentCandidate,
    MatcherSpec,
    match_correspondent,
)


def _contains_matchers(*patterns: str) -> tuple[MatcherSpec, ...]:
    return tuple(MatcherSpec(kind="contains", pattern=p, scope="both", priority=100) for p in patterns)


VODAFONE_ID = uuid.uuid4()
HUK_ID = uuid.uuid4()
FINANZAMT_ID = uuid.uuid4()
TECHEM_ID = uuid.uuid4()


def _seed_candidates() -> list[CorrespondentCandidate]:
    return [
        CorrespondentCandidate(
            correspondent_id=VODAFONE_ID,
            name="Vodafone GmbH",
            short_name="Vodafone",
            aliases=("Vodafone", "Red Plus", "GigaKombi"),
            matchers=_contains_matchers("Vodafone", "Red Plus", "GigaKombi"),
        ),
        CorrespondentCandidate(
            correspondent_id=HUK_ID,
            name="HUK-Coburg",
            short_name="HUK",
            aliases=("HUK", "HUK-Coburg", "Privathaftpflicht"),
            matchers=_contains_matchers("HUK", "HUK-Coburg", "Privathaftpflicht"),
        ),
        CorrespondentCandidate(
            correspondent_id=FINANZAMT_ID,
            name="Finanzamt Kiel",
            short_name="FA Kiel",
            aliases=("Finanzamt", "ELSTER", "Einkommensteuerbescheid", "Lohnsteuer"),
            matchers=_contains_matchers("Finanzamt", "ELSTER", "Einkommensteuerbescheid", "Lohnsteuer"),
        ),
        CorrespondentCandidate(
            correspondent_id=TECHEM_ID,
            name="Techem",
            short_name="Techem",
            aliases=("Techem", "Heizkosten"),
            matchers=_contains_matchers("Techem", "Heizkosten"),
        ),
    ]


class CorrespondentMatchingTest(unittest.TestCase):
    def test_exact_canonical_name(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="Vodafone GmbH")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, VODAFONE_ID)
        self.assertEqual(match.matched_by, "name")

    def test_alias_resolves_to_canonical(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="Red Plus")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, VODAFONE_ID)
        self.assertEqual(match.matched_by, "alias")

    def test_hyphenated_name(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="HUK-Coburg")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, HUK_ID)

    def test_elster_resolves_to_finanzamt(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="ELSTER")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, FINANZAMT_ID)

    def test_case_insensitive_alias(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="vodafone")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, VODAFONE_ID)

    def test_sender_contains_alias(self) -> None:
        # Roher Absender mit Zusatz: Alias "Vodafone" steckt als Teilstring darin.
        match = match_correspondent(_seed_candidates(), sender="Vodafone Kabel Deutschland")
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, VODAFONE_ID)

    def test_matcher_hits_ocr_text_when_no_sender(self) -> None:
        match = match_correspondent(
            _seed_candidates(),
            sender=None,
            ocr_text="... Ihre Heizkostenabrechnung für das Abrechnungsjahr 2024 ...",
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.correspondent_id, TECHEM_ID)
        self.assertEqual(match.matched_by, "matcher")

    def test_no_match_returns_none(self) -> None:
        match = match_correspondent(_seed_candidates(), sender="Völlig Unbekannt AG")
        self.assertIsNone(match)

    def test_empty_input_returns_none(self) -> None:
        self.assertIsNone(match_correspondent(_seed_candidates(), sender="   "))

    def test_regex_matcher(self) -> None:
        candidates = [
            CorrespondentCandidate(
                correspondent_id=VODAFONE_ID,
                name="Vodafone GmbH",
                short_name="Vodafone",
                aliases=(),
                matchers=(MatcherSpec(kind="regex", pattern=r"red\s*plus", scope="both", priority=120),),
            )
        ]
        match = match_correspondent(candidates, sender="Mein RedPlus Tarif")
        self.assertIsNotNone(match)
        self.assertEqual(match.matched_by, "matcher")

    def test_invalid_regex_is_skipped(self) -> None:
        candidates = [
            CorrespondentCandidate(
                correspondent_id=VODAFONE_ID,
                name="Vodafone GmbH",
                matchers=(MatcherSpec(kind="regex", pattern=r"([unclosed", scope="both", priority=100),),
            )
        ]
        # Darf nicht crashen, nur kein Treffer.
        self.assertIsNone(match_correspondent(candidates, sender="irgendwas"))


if __name__ == "__main__":
    unittest.main()

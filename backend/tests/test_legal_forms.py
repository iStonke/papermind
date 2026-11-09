import json
import unittest
from pathlib import Path

from app.services.legal_forms import (
    canonicalize_legal_form,
    contains_legal_form,
    cut_at_legal_form,
    legal_form_key,
    names_equivalent,
    split_legal_form,
)

_CASES = json.loads((Path(__file__).parent / "fixtures" / "legal_forms.json").read_text(encoding="utf-8"))


class LegalFormsTest(unittest.TestCase):
    def test_split_shared_cases(self) -> None:
        for value, base, legal_form in _CASES["split"]:
            with self.subTest(value=value):
                split = split_legal_form(value)
                self.assertEqual(split.base, base)
                self.assertEqual(split.legal_form, legal_form)

    def test_equivalence_shared_cases(self) -> None:
        for left, right, expected in _CASES["equivalent"]:
            with self.subTest(left=left, right=right):
                self.assertEqual(names_equivalent(left, right), expected)
                self.assertEqual(names_equivalent(right, left), expected)

    def test_cut_shared_cases(self) -> None:
        for value, expected in _CASES["cut"]:
            with self.subTest(value=value):
                self.assertEqual(cut_at_legal_form(value), expected)

    def test_contains_shared_cases(self) -> None:
        for value, expected in _CASES["contains"]:
            with self.subTest(value=value):
                self.assertEqual(contains_legal_form(value), expected)

    def test_canonical_spelling_and_key(self) -> None:
        self.assertEqual(canonicalize_legal_form("Vodafone gmbh."), "Vodafone GmbH")
        self.assertEqual(canonicalize_legal_form("Sportverein eV"), "Sportverein e.V.")
        self.assertEqual(legal_form_key("VODAFONE GmbH"), "vodafone")
        self.assertEqual(legal_form_key("Möller GmbH"), legal_form_key("Möller"))


if __name__ == "__main__":
    unittest.main()

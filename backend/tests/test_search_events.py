import unittest

from app.services.search_events import MAX_TERM_LENGTH, SearchEventService


class SearchEventNormalizeTest(unittest.TestCase):
    def test_collapses_whitespace(self) -> None:
        self.assertEqual(SearchEventService.normalize("  Rechnung   2024 "), "Rechnung 2024")

    def test_empty_and_none(self) -> None:
        self.assertEqual(SearchEventService.normalize(""), "")
        self.assertEqual(SearchEventService.normalize(None), "")
        self.assertEqual(SearchEventService.normalize("   "), "")

    def test_truncates_to_max_length(self) -> None:
        long_term = "a" * (MAX_TERM_LENGTH + 50)
        self.assertEqual(len(SearchEventService.normalize(long_term)), MAX_TERM_LENGTH)


if __name__ == "__main__":
    unittest.main()

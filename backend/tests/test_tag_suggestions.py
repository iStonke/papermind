import unittest
from unittest import mock

from app.services import tag_suggestions


class TagSuggestionsTest(unittest.TestCase):
    def test_explicit_empty_result_does_not_turn_into_fallback_tags(self) -> None:
        with mock.patch("app.services.tag_suggestions.httpx.post") as post:
            post.return_value.json.return_value = {"answer": '["Keine Tags gefunden"]'}
            post.return_value.raise_for_status.return_value = None

            result = tag_suggestions.suggest_tags_with_ai(
                "Rechnung der Musterfirma für den Monat Juli",
                max_tags=3,
                max_text_chars=8000,
                ai_base_url="http://ai:8080",
                timeout_seconds=1,
            )

        self.assertEqual(result, [])

    def test_unavailable_ai_uses_local_fallback(self) -> None:
        with mock.patch(
            "app.services.tag_suggestions.httpx.post",
            side_effect=tag_suggestions.httpx.ConnectError("offline"),
        ):

            result = tag_suggestions.suggest_tags_with_ai(
                "Versicherung Versicherung Vertrag Vertrag Vertrag",
                max_tags=2,
                max_text_chars=8000,
                ai_base_url="http://ai:8080",
                timeout_seconds=1,
            )

        self.assertEqual(result, ["Vertrag", "Versicherung"])

    def test_explanatory_free_text_uses_local_fallback(self) -> None:
        with mock.patch("app.services.tag_suggestions.httpx.post") as post:
            post.return_value.json.return_value = {"answer": "Hier ist keine strukturierte Tag Liste"}
            post.return_value.raise_for_status.return_value = None

            result = tag_suggestions.suggest_tags_with_ai(
                "Versicherung Versicherung Vertrag Vertrag Vertrag",
                max_tags=2,
                max_text_chars=8000,
                ai_base_url="http://ai:8080",
                timeout_seconds=1,
            )

        self.assertEqual(result, ["Vertrag", "Versicherung"])

    def test_blocked_candidates_are_filtered_case_insensitively(self) -> None:
        candidates, had_explicit_answer = tag_suggestions.parse_tag_candidates(
            '["Rechnung", "keine Informationen gefunden", "rechnung", "KFZ"]',
            max_tags=3,
        )

        self.assertTrue(had_explicit_answer)
        self.assertEqual(candidates, ["Rechnung", "KFZ"])


if __name__ == "__main__":
    unittest.main()

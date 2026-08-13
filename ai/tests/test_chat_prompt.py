import unittest

from app.main import ChatContext, _build_chat_messages


class ChatPromptTest(unittest.TestCase):
    def test_backend_template_is_forwarded_without_duplicate_context(self) -> None:
        template = "DOKUMENTKONTEXT:\\nAuszug mit Zahlungsfrist.\\n\\nFRAGE:\\nWann zahlen?\\n\\nFORMAT: Kurz."
        messages = _build_chat_messages(
            "Wann zahlen?",
            [ChatContext(text="Auszug mit Zahlungsfrist.", page_from=2)],
            "Nur aus dem Kontext antworten.",
            template,
        )

        self.assertEqual(messages[0]["content"], "Nur aus dem Kontext antworten.")
        self.assertEqual(messages[1]["content"], template)
        self.assertEqual(messages[1]["content"].count("Auszug mit Zahlungsfrist."), 1)

    def test_direct_call_keeps_safe_context_fallback(self) -> None:
        messages = _build_chat_messages(
            "Wann zahlen?",
            [ChatContext(text="Zahlbar bis 15. August.", page_from=2)],
            None,
            None,
        )

        self.assertIn("Zahlbar bis 15. August.", messages[1]["content"])
        self.assertIn("Wann zahlen?", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.notes import NoteTextGenerationRequest
from app.schemas.settings import NOTE_WRITING_SYSTEM_PROMPT_DEFAULT
from app.services.note_ai import GenerationPlan, NoteAIService


def runtime_settings(*, provider: str = "openai") -> SimpleNamespace:
    return SimpleNamespace(
        text_generation=SimpleNamespace(
            enabled=True,
            provider=provider,
            ollama_model="local-writer",
            openai_model="openai-writer",
            anthropic_model="claude-writer",
            system_prompt="Eigene interne Schreibanweisung für Notizen mit deutlich mehr als fünfzig Zeichen.",
            note_context_chars=6000,
            max_output_tokens=900,
            temperature=0.35,
        ),
        ollama=SimpleNamespace(
            enabled=True,
            base_url="http://ollama:11434",
            timeout_seconds=90,
            chat_model="local-knowledge",
        ),
    )


class NoteAIServiceTest(unittest.TestCase):
    def test_writing_prompt_requests_valid_markdown_lists(self) -> None:
        self.assertIn('Listenpunkt beginnt in einer eigenen Zeile mit „- “', NOTE_WRITING_SYSTEM_PROMPT_DEFAULT)

    @patch("app.services.note_ai.AICredentialService.get_key", return_value="cloud-secret")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings())
    def test_plain_note_text_may_use_configured_cloud_provider(self, _settings, _key) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = service.prepare(NoteTextGenerationRequest(instruction="Schreibe weiter", note_context="Notiz"))

        self.assertEqual(plan.provider, "openai")
        self.assertEqual(plan.model, "openai-writer")
        self.assertEqual(
            plan.system_prompt,
            "Eigene interne Schreibanweisung für Notizen mit deutlich mehr als fünfzig Zeichen.",
        )
        self.assertFalse(plan.local_only)

    @patch("app.services.note_ai.AICredentialService.get_key")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings(provider="anthropic"))
    def test_document_context_forces_ollama_without_reading_cloud_key(self, _settings, get_key) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = service.prepare(
            NoteTextGenerationRequest(
                instruction="Erstelle einen Absatz",
                note_context="Notiz",
                document_context="Bibliotheksinhalt",
            )
        )

        self.assertEqual(plan.provider, "ollama")
        self.assertEqual(plan.model, "local-writer")
        self.assertTrue(plan.local_only)
        get_key.assert_not_called()

    def test_stream_exposes_attribution_and_deltas_as_ndjson(self) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = GenerationPlan(
            provider="ollama",
            model="local-writer",
            system_prompt="system",
            user_prompt="user",
            api_key="",
            base_url="http://ollama",
            timeout_seconds=10,
            max_output_tokens=100,
            temperature=0.3,
            local_only=False,
        )
        with patch.object(service, "_provider_stream", return_value=iter(["Hallo", " Welt"])):
            events = [json.loads(line) for line in service.stream(plan)]

        self.assertEqual(events[0]["type"], "meta")
        self.assertEqual(events[0]["provider"], "ollama")
        self.assertEqual("".join(event.get("text", "") for event in events), "Hallo Welt")
        self.assertEqual(events[-1]["type"], "done")

    def test_document_knowledge_service_cannot_read_note_cloud_provider_settings(self) -> None:
        service_source = Path(__file__).parents[1] / "app" / "services" / "ai.py"
        source = service_source.read_text(encoding="utf-8")

        self.assertNotIn("text_generation", source)
        self.assertIn("chat_model=runtime_settings.ollama.chat_model", source)


if __name__ == "__main__":
    unittest.main()

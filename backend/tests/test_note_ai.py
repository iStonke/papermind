import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.schemas.notes import NoteTextGenerationRequest
from app.schemas.settings import NOTE_WRITING_SYSTEM_PROMPT_DEFAULT
from app.services.note_ai import GenerationPlan, NoteAIProviderError, NoteAIService, _user_prompt


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
    def test_whole_note_context_keeps_beginning_despite_cursor_context_limit(self) -> None:
        text = 'Anfang der Notiz. ' + 'Text ' * 1500 + 'Ende.'
        payload = NoteTextGenerationRequest(instruction='Zusammenfassen', note_context=text, context_scope='note')
        prompt = _user_prompt(payload, 6000)
        self.assertIn('GANZE NOTIZ:\n' + text, prompt)
        payload.context_scope = 'before'
        self.assertNotIn('Anfang der Notiz.', _user_prompt(payload, 6000))

    def test_writing_prompt_requests_valid_markdown_lists(self) -> None:
        self.assertIn('Listenpunkt beginnt in einer eigenen Zeile mit „- “', NOTE_WRITING_SYSTEM_PROMPT_DEFAULT)

    @patch("app.services.note_ai.AICredentialService.get_key", return_value="cloud-secret")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings())
    def test_plain_note_text_may_use_configured_cloud_provider(self, _settings, _key) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = service.prepare(
            NoteTextGenerationRequest(
                instruction="Schreibe weiter",
                length_instruction="1–2 Sätze",
                note_context="Notiz",
            )
        )

        self.assertEqual(plan.provider, "openai")
        self.assertEqual(plan.model, "openai-writer")
        self.assertTrue(plan.system_prompt.startswith(
            "Eigene interne Schreibanweisung für Notizen mit deutlich mehr als fünfzig Zeichen.\n\n"
        ))
        self.assertIn("EDITOR-FORMAT:", plan.system_prompt)
        self.assertIn("genau 10 solche Zeilen", plan.system_prompt)
        self.assertIn("- [ ] Text", plan.system_prompt)
        self.assertFalse(plan.local_only)
        self.assertEqual(plan.fallback_model, "local-writer")
        self.assertIn("VERBINDLICHE LÄNGENVORGABE:\n1–2 Sätze", plan.user_prompt)
        self.assertIn("keinen zusätzlichen Vor- oder Nachsatz", plan.user_prompt)

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

    def test_cloud_failure_falls_back_to_local_model_before_first_delta(self) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = GenerationPlan(
            provider="openai",
            model="cloud-writer",
            system_prompt="system",
            user_prompt="user",
            api_key="secret",
            base_url="http://ollama",
            timeout_seconds=10,
            max_output_tokens=100,
            temperature=0.3,
            local_only=False,
            fallback_model="local-writer",
        )

        def provider_stream(active_plan):
            if active_plan.provider == "openai":
                raise NoteAIProviderError("Cloud nicht verfügbar")
            return iter(["Lokale Antwort"])

        with patch.object(service, "_provider_stream_with_retry", side_effect=provider_stream):
            events = [json.loads(line) for line in service.stream(plan)]

        meta = [event for event in events if event["type"] == "meta"]
        self.assertEqual([event["provider"] for event in meta], ["openai", "ollama"])
        self.assertEqual(meta[-1]["fallback_from"], "openai")
        self.assertEqual("".join(event.get("text", "") for event in events), "Lokale Antwort")
        self.assertEqual(events[-1]["type"], "done")

    def test_openai_writing_request_disables_reasoning_and_reads_stream_deltas(self) -> None:
        plan = GenerationPlan(
            provider="openai",
            model="gpt-writer",
            system_prompt="system",
            user_prompt="user",
            api_key="secret",
            base_url="http://ollama",
            timeout_seconds=10,
            max_output_tokens=100,
            temperature=0.3,
            local_only=False,
        )
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = [
            'event: response.output_text.delta',
            'data: {"type":"response.output_text.delta","delta":"Hallo"}',
            'data: {"type":"response.completed"}',
        ]
        response.raise_for_status.return_value = None

        with patch("app.services.note_ai.httpx.stream", return_value=response) as stream:
            deltas = list(NoteAIService._openai_stream(plan))

        self.assertEqual(deltas, ["Hallo"])
        self.assertEqual(stream.call_args.kwargs["json"]["reasoning"], {"effort": "none"})

    def test_openai_stream_failure_event_is_not_misreported_as_empty_text(self) -> None:
        plan = GenerationPlan(
            provider="openai",
            model="gpt-writer",
            system_prompt="system",
            user_prompt="user",
            api_key="secret",
            base_url="http://ollama",
            timeout_seconds=10,
            max_output_tokens=100,
            temperature=0.3,
            local_only=False,
        )
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = [
            'data: {"type":"response.failed","response":{"error":{"code":"model_error"}}}',
        ]
        response.raise_for_status.return_value = None

        with patch("app.services.note_ai.httpx.stream", return_value=response):
            with self.assertRaisesRegex(NoteAIProviderError, "OpenAI"):
                list(NoteAIService._openai_stream(plan))

    def test_document_knowledge_service_cannot_read_note_cloud_provider_settings(self) -> None:
        service_source = Path(__file__).parents[1] / "app" / "services" / "ai.py"
        source = service_source.read_text(encoding="utf-8")

        self.assertNotIn("text_generation", source)
        self.assertIn("chat_model=runtime_settings.ollama.chat_model", source)


if __name__ == "__main__":
    unittest.main()

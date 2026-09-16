import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.note_review_prompt import NOTE_REVIEW_SCHEMA
from app.schemas.notes import NoteReviewRequest, NoteTextGenerationRequest
from app.schemas.settings import NOTE_WRITING_SYSTEM_PROMPT_DEFAULT
from app.services.note_ai import GenerationPlan, NoteAIIncompleteError, NoteAIProviderError, NoteAIService, _user_prompt


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

    @patch("app.services.note_ai.AICredentialService.get_key", return_value="cloud-secret")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings())
    def test_review_pins_json_prompt_and_clamps_temperature(self, _settings, _key) -> None:
        service = NoteAIService(db=object(), owner_id=None)
        plan = service.prepare_review(
            NoteReviewRequest(note_text="meeting 12.03 mit holger", extra_instruction="  kürzer  ")
        )

        self.assertEqual(plan.provider, "openai")
        self.assertEqual(plan.model, "openai-writer")
        # The review path must NOT carry the editor-markdown grammar; it needs JSON.
        self.assertNotIn("EDITOR-FORMAT:", plan.system_prompt)
        self.assertIn("AUSSCHLIESSLICH mit gültigem JSON", plan.system_prompt)
        self.assertIn('"changes"', plan.system_prompt)
        # cfg.temperature is 0.35; the review path clamps to <= 0.2 for stable JSON.
        self.assertEqual(plan.temperature, 0.2)
        self.assertFalse(plan.local_only)
        self.assertTrue(plan.json_output)
        self.assertEqual(plan.max_output_tokens, 4096)
        self.assertEqual(plan.fallback_model, "local-writer")
        self.assertIn("NOTIZTEXT:\nmeeting 12.03 mit holger", plan.user_prompt)
        self.assertIn("ZUSÄTZLICHE ANWEISUNG DES NUTZERS:\nkürzer", plan.user_prompt)

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

    def test_json_output_forces_structured_json_on_ollama_and_openai(self) -> None:
        base = dict(
            model="m", system_prompt="s", user_prompt="u", api_key="secret",
            base_url="http://ollama", timeout_seconds=10, max_output_tokens=100,
            temperature=0.2, local_only=False,
        )
        ollama_plan = GenerationPlan(provider="ollama", json_output=True, **{**base, "api_key": ""})
        openai_plan = GenerationPlan(provider="openai", json_output=True, **base)
        writing_plan = GenerationPlan(provider="ollama", **{**base, "api_key": ""})

        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = []
        response.raise_for_status.return_value = None

        with patch("app.services.note_ai.httpx.stream", return_value=response) as stream:
            list(NoteAIService._ollama_stream(ollama_plan))
            self.assertEqual(stream.call_args.kwargs["json"]["format"], NOTE_REVIEW_SCHEMA)
            list(NoteAIService._ollama_stream(writing_plan))
            self.assertNotIn("format", stream.call_args.kwargs["json"])
            list(NoteAIService._openai_stream(openai_plan))
            self.assertEqual(stream.call_args.kwargs["json"]["text"], {"format": {"type": "json_object"}})

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


class ReviewProviderHardeningTests(unittest.TestCase):
    def plan(self, provider="anthropic", json_output=True):
        return GenerationPlan(provider=provider, model="test", system_prompt="s", user_prompt="u",
                              api_key="test", base_url="http://ollama", timeout_seconds=10,
                              max_output_tokens=4096, temperature=0.2, local_only=False,
                              json_output=json_output)

    def response(self, events, *, sse=True):
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = [("data: " if sse else "") + json.dumps(e) for e in events]
        return response

    @patch("app.services.note_ai.AICredentialService.get_key", return_value="test")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings())
    def test_review_receives_existing_structure_and_transformation_contract(self, _settings, _key):
        payload = NoteReviewRequest(note_text="Titel", note_structure=[{
            "id": "b1", "type": "heading", "text": "Titel", "convertible": True,
            "structure": [{"type": "heading", "level": 2}],
        }])
        plan = NoteAIService(db=object(), owner_id=None).prepare_review(payload)
        self.assertIn('"id":"b1"', plan.user_prompt)
        self.assertIn('"level":2', plan.user_prompt)
        for term in ["block_ids", "Hinweisblock", "Tabelle", "Fließtext", "keine neuen Fakten"]:
            self.assertIn(term, plan.system_prompt)
        self.assertIn("block_ids", NOTE_REVIEW_SCHEMA["properties"]["changes"]["items"]["properties"])

    def test_anthropic_review_collects_only_the_named_tool_input(self):
        events = [
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hier die Antwort:"}},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "name": "submit_review"}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"changes":'}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '[]}'}},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
        ]
        with patch("app.services.note_ai.httpx.stream", return_value=self.response(events)) as stream:
            self.assertEqual("".join(NoteAIService._anthropic_stream(self.plan())), '{"changes":[]}')
            payload = stream.call_args.kwargs["json"]
            self.assertEqual(payload["tools"][0]["input_schema"], NOTE_REVIEW_SCHEMA)
            self.assertEqual(payload["tool_choice"]["name"], "submit_review")

    def test_anthropic_writing_keeps_text_streaming(self):
        events = [{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Text"}}]
        with patch("app.services.note_ai.httpx.stream", return_value=self.response(events)) as stream:
            self.assertEqual(list(NoteAIService._anthropic_stream(self.plan(json_output=False))), ["Text"])
            self.assertNotIn("tools", stream.call_args.kwargs["json"])

    def test_truncation_is_reported_with_a_retryable_code_and_no_done(self):
        service = NoteAIService(db=object(), owner_id=None)
        for provider, events, method in [
            ("anthropic", [{"type": "message_delta", "delta": {"stop_reason": "max_tokens"}}], "_anthropic_stream"),
            ("ollama", [{"done": True, "done_reason": "length"}], "_ollama_stream"),
            ("openai", [{"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}}], "_openai_stream"),
        ]:
            with self.subTest(provider=provider):
                with patch("app.services.note_ai.httpx.stream", return_value=self.response(events, sse=provider != "ollama")):
                    with self.assertRaises(NoteAIIncompleteError):
                        list(getattr(service, method)(self.plan(provider)))
        with patch.object(service, "_provider_stream_with_retry", side_effect=NoteAIIncompleteError("Abgeschnitten")):
            events = [json.loads(line) for line in service.stream(self.plan())]
        self.assertEqual(events[-1]["code"], "review_incomplete")
        self.assertNotIn("done", [event["type"] for event in events])

    @patch("app.services.note_ai.AICredentialService.get_key", return_value="test")
    @patch("app.services.note_ai.SettingsService.get_settings", return_value=runtime_settings())
    def test_retry_asks_for_a_short_complete_result(self, _settings, _key):
        plan = NoteAIService(db=object(), owner_id=None).prepare_review(NoteReviewRequest(note_text="Text", retry=True))
        self.assertIn("höchstens 6", plan.system_prompt)
        self.assertEqual(plan.max_output_tokens, 4096)


if __name__ == "__main__":
    unittest.main()

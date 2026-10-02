import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.core.errors import BadRequestError, NotFoundError
from app.services.note_ai import GenerationPlan, NoteAIProviderError
from app.services.thought_summary import SUMMARY_SCHEMA, ThoughtSummaryService


def generation_plan():
    return GenerationPlan(provider="ollama", model="test", system_prompt="system",
                          user_prompt="user", api_key="", base_url="http://ollama",
                          timeout_seconds=30, max_output_tokens=900,
                          temperature=.7, local_only=False)


def answer(title=" Projektideen ", content=" Zusammenfassung "):
    return iter([json.dumps({"type": "delta", "text": json.dumps({"title": title, "content": content})}),
                 json.dumps({"type": "done"})])


class ThoughtSummaryTest(unittest.TestCase):
    def setUp(self):
        pins_patch = patch("app.services.thought_summary.NotePinService")
        ai_patch = patch("app.services.thought_summary.NoteAIService")
        self.pins = pins_patch.start().return_value
        self.ai = ai_patch.start().return_value
        self.addCleanup(pins_patch.stop)
        self.addCleanup(ai_patch.stop)
        self.room = SimpleNamespace(id=uuid.uuid4(), collection_id=uuid.uuid4(), title="Arbeit")
        self.pins.get_room.return_value = self.room
        self.pins.list.return_value = [SimpleNamespace(text="Idee eins"), SimpleNamespace(text="Idee zwei")]
        self.ai.prepare.return_value = generation_plan()
        self.ai.stream.return_value = answer()
        self.service = ThoughtSummaryService(object(), uuid.uuid4())

    def test_preview_includes_every_thought_and_generated_title_without_mutation(self):
        result = self.service.summarize(self.room.id)
        self.assertEqual((result.title, result.content), ("Projektideen", "Zusammenfassung"))
        self.pins.get_room.assert_called_once_with(self.room.id)
        self.pins.list.assert_called_once_with(self.room.collection_id, room_id=self.room.id)
        plan = self.ai.stream.call_args.args[0]
        source = json.loads(plan.user_prompt.split("\n", 1)[1])
        self.assertIn("Idee eins", source["gedanken"])
        self.assertIn("Idee zwei", source["gedanken"])
        self.assertEqual(plan.json_schema, SUMMARY_SCHEMA)
        self.assertTrue(plan.json_output)
        self.assertGreaterEqual(plan.max_output_tokens, 4096)
        self.assertEqual([call[0] for call in self.pins.mock_calls], ["get_room", "list"])

    def test_foreign_room_is_rejected_before_ai_generation(self):
        self.pins.get_room.side_effect = NotFoundError("Sammlung nicht gefunden")
        with self.assertRaises(NotFoundError):
            self.service.summarize(self.room.id)
        self.ai.prepare.assert_not_called()
        self.ai.stream.assert_not_called()

    def test_empty_room_is_rejected_without_ai_call(self):
        self.pins.list.return_value = []
        with self.assertRaises(BadRequestError):
            self.service.summarize(self.room.id)
        self.ai.prepare.assert_not_called()

    def test_large_room_does_not_drop_middle_or_tail(self):
        texts = ["ANFANG " + "a" * 16000, "MITTE " + "b" * 14000, "ENDE der Gedanken"]
        self.pins.list.return_value = [SimpleNamespace(text=text) for text in texts]
        sources = []
        def generate(plan):
            sources.append(json.loads(plan.user_prompt.split("\n", 1)[1]))
            return answer("Teil", "Verdichtete Gedanken")
        self.ai.stream.side_effect = generate
        self.service.summarize(self.room.id)
        original = "".join(source for source in sources if isinstance(source, str))
        for text in texts:
            self.assertIn(text, original)
        self.assertIsInstance(sources[-1], dict)
        self.assertIn("Verdichtete Gedanken", sources[-1]["gedanken"])

    def test_invalid_or_blank_answer_is_never_offered_as_a_note(self):
        for output in ("not JSON", '{"title":"","content":"Text"}', '{"title":"Titel","content":"   "}'):
            with self.subTest(output=output):
                self.ai.stream.return_value = iter([json.dumps({"type": "delta", "text": output}), json.dumps({"type": "done"})])
                with self.assertRaises(NoteAIProviderError):
                    self.service.summarize(self.room.id)

    def test_incomplete_or_failed_generation_is_rejected(self):
        for events in ([{"type": "delta", "text": '{"title":"Titel","content":"Text"}'}],
                       [{"type": "error", "message": "Modell nicht erreichbar"}]):
            with self.subTest(events=events):
                self.ai.stream.return_value = iter(json.dumps(event) for event in events)
                with self.assertRaises(NoteAIProviderError):
                    self.service.summarize(self.room.id)

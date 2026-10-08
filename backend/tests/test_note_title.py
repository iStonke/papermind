import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from app.core.errors import ConflictError, NotFoundError
from app.services.note_title import NoteTitleService, title_content, enough_title_content

class NoteTitleTest(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.scalars.return_value.all.return_value = [SimpleNamespace(title='Bestehender Titel', notebook_id=None, collection_id='same')]
        self.db.scalar.return_value = None
        self.note = SimpleNamespace(id=uuid.uuid4(), revision=3, title='', is_deleted=False, is_template=False,
            notebook_id=None, collection_id='same', body_json={'type':'doc','content':[{'type':'text','text':'Inhalt ' * 90}]})
        for target in ['NoteService','SettingsService','NoteAIService']:
            mock = patch('app.services.note_title.' + target)
            setattr(self, target, mock.start().return_value)
            self.addCleanup(mock.stop)
        self.NoteService._get.return_value = self.note
        self.SettingsService.get_settings.return_value = SimpleNamespace(
            ollama=SimpleNamespace(enabled=True, base_url='http://local:11434', timeout_seconds=30),
            text_generation=SimpleNamespace(provider='openai', ollama_model='local-model'))
        self.NoteAIService.stream.return_value = [json.dumps({'type':'delta','text':'{"title":"Lokaler Titel"}'}), json.dumps({'type':'done'})]
        self.service = NoteTitleService(self.db, uuid.uuid4())

    def test_local_only_existing_titles_and_no_write(self):
        self.assertEqual(self.service.suggest(self.note.id, 3)['title'], 'Lokaler Titel')
        plan = self.NoteAIService.stream.call_args.args[0]
        self.assertEqual(plan.provider, 'ollama')
        self.assertTrue(plan.local_only)
        self.assertEqual(plan.api_key, '')
        self.assertEqual(plan.fallback_model, '')
        self.assertIn('Bestehender Titel', plan.user_prompt)
        self.db.commit.assert_not_called()
        self.assertEqual(self.note.title, '')

    def test_manual_titles_and_short_notes_skip_ai(self):
        self.note.title = 'Mein Titel'
        self.assertIsNone(self.service.suggest(self.note.id, 3)['title'])
        self.note.title = ''
        self.note.body_json = {'type':'text','text':'Kurz'}
        self.assertIsNone(self.service.suggest(self.note.id, 3)['title'])
        self.NoteAIService.stream.assert_not_called()

    def test_stale_or_foreign_note_rejected(self):
        with self.assertRaises(ConflictError): self.service.suggest(self.note.id, 2)
        self.NoteService._get.return_value = None
        with self.assertRaises(NotFoundError): self.service.suggest(self.note.id, 3)
        self.NoteAIService.stream.assert_not_called()

    def test_disabled_local_ai_does_not_use_cloud(self):
        self.SettingsService.get_settings.return_value.ollama.enabled = False
        self.assertIsNone(self.service.suggest(self.note.id, 3)['title'])
        self.NoteAIService.stream.assert_not_called()

    def test_duplicate_title_is_not_applied(self):
        self.db.scalar.return_value = uuid.uuid4()
        self.assertIsNone(self.service.suggest(self.note.id, 3)['title'])

    def test_content_changed_during_generation_discards_result(self):
        self.db.refresh.side_effect = lambda note: setattr(note, 'revision', 4)
        self.assertIsNone(self.service.suggest(self.note.id, 3)['title'])

    def test_content_includes_own_note_but_not_filename(self):
        text = title_content({'type':'ocrQuote','attrs':{'text':'Zitat','ownNote':'Gedanke','docTitle':'Dateiname.pdf'}})
        self.assertEqual(text, 'Zitat Gedanke')
        self.assertFalse(enough_title_content(text))

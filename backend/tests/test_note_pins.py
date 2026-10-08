import unittest
import uuid
from sqlalchemy import text
from pydantic import ValidationError
from app.core.errors import ConflictError, NotFoundError
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.notes import CollectionCreateRequest
from app.schemas.note_pins import PinCreateRequest, PinPositionRequest, PinRead, PinUpdateRequest, PinColorBatchRequest, PinPositionBatchRequest, PinPositionItem
from app.services.note_collection_service import NoteCollectionService
from app.services.note_pin_service import NotePinService, hashtag_names
from unittest.mock import patch

class HashtagTest(unittest.TestCase):
    def test_unicode_duplicates_and_urls(self):
        self.assertEqual(hashtag_names('Idee #Übergabe #übergabe #Team-Arbeit https://x/#fragment abc#nein #123'), ['Übergabe', 'Team-Arbeit'])

    def test_empty_text_rejected(self):
        with self.assertRaises(ValidationError):
            PinCreateRequest(text=' \n ', collection_id=uuid.uuid4())

class NotePinsTest(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.users = [User(username=f'pin-test-{uuid.uuid4().hex}', password_hash='x', is_admin=False, is_active=True) for _ in range(2)]
        self.db.add_all(self.users)
        self.db.commit()
        self.owner, self.other = [u.id for u in self.users]
        self.collections = NoteCollectionService(self.db, self.owner)
        self.a = self.collections.create_collection(CollectionCreateRequest(name='Arbeit'))
        self.b = self.collections.create_collection(CollectionCreateRequest(name='Privat'))
        self.other_collection = NoteCollectionService(self.db, self.other).ensure_default_id()
        self.service = NotePinService(self.db, self.owner)

    def test_global_rooms_and_pins_include_all_collections_but_only_owner(self):
        first = self.create(self.a.id, 'Arbeit')
        second = self.create(self.b.id, 'Privat')
        NotePinService(self.db, self.other).create(PinCreateRequest(collection_id=self.other_collection, text='Fremd'))
        self.assertEqual({pin.id for pin in self.service.list(None)}, {first.id, second.id})
        self.assertEqual({room.collection_id for room in self.service.rooms()}, {self.a.id, self.b.id})
        self.assertEqual({pin.id for pin in self.service.list(self.a.id)}, {first.id})

    def test_generated_title_is_persisted_and_manual_edit_clears_origin(self):
        from app.services.note_service import NoteService
        from app.schemas.notes import NoteCreateRequest, NoteUpdateRequest, NoteRead
        service = NoteService(self.db, self.owner)
        note = service.create_note(NoteCreateRequest(collection_id=self.a.id))
        generated = service.update_note(note.id, NoteUpdateRequest(title='KI-Titel', title_is_generated=True, base_revision=note.revision))
        self.assertTrue(NoteRead.model_validate(generated).title_is_generated)
        self.assertTrue(next(item for item in service.list_notes() if item.id == note.id).title_is_generated)
        manual = service.update_note(note.id, NoteUpdateRequest(title='Mein Titel', base_revision=generated.revision))
        self.assertFalse(manual.title_is_generated)

    def tearDown(self):
        self.db.rollback()
        for owner in (self.owner, self.other):
            for table in ('note_pin', 'note', 'note_collection', 'tags', 'users'):
                key = 'id' if table == 'users' else 'owner_id'
                self.db.execute(text(f'DELETE FROM {table} WHERE {key} = :owner'), {'owner': owner})
        self.db.commit()
        self.db.close()

    def create(self, collection=None, content='Gedanke #Übergabe'):
        return self.service.create(PinCreateRequest(collection_id=collection or self.a.id, text=content))

    def test_summary_only_reads_open_thoughts_of_the_owned_room(self):
        from app.services.thought_summary import ThoughtSummaryService
        from tests.test_thought_summary import answer, generation_plan
        first = self.create(content='Erster aktiver Gedanke')
        second = self.create(content='Zweiter aktiver Gedanke')
        archived = self.create(content='Archivierter Gedanke')
        self.service.archive(self.a.id, [archived.id])
        other_room = self.service.create_room(self.a.id, 'Andere Fläche')
        self.service.create(PinCreateRequest(collection_id=self.a.id, room_id=other_room.id, text='Anderer Raum'))
        before_notes = self.db.scalar(text('SELECT count(*) FROM note WHERE owner_id = :owner'), {'owner': self.owner})
        before = (first.text, first.updated_at, second.text, second.updated_at)
        with patch('app.services.thought_summary.NoteAIService') as ai:
            ai.return_value.prepare.return_value = generation_plan()
            ai.return_value.stream.return_value = answer()
            ThoughtSummaryService(self.db, self.owner).summarize(first.room_id)
            prompt = ai.return_value.stream.call_args.args[0].user_prompt
        self.assertIn(first.text, prompt)
        self.assertIn(second.text, prompt)
        self.assertNotIn(archived.text, prompt)
        self.assertNotIn('Anderer Raum', prompt)
        self.db.expire_all()
        self.assertEqual((first.text, first.updated_at, second.text, second.updated_at), before)
        self.assertEqual(self.db.scalar(text('SELECT count(*) FROM note WHERE owner_id = :owner'), {'owner': self.owner}), before_notes)

    def test_summary_transfer_api_requires_document_and_persists_title_and_content(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.deps import get_current_user
        from app.core.errors import install_exception_handlers
        from app.db import get_db
        from app.routers.notes import router
        from app.services.note_service import NoteService
        original = self.create(content='Originaler Gedanke bleibt erhalten')
        app = FastAPI()
        app.include_router(router)
        install_exception_handlers(app)
        app.dependency_overrides[get_current_user] = lambda: self.users[0]
        app.dependency_overrides[get_db] = lambda: self.db
        nodes = [
            {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': 'Nächste Schritte'}]},
            {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [
                {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Mein ergänzter Gedanke'}]}
            ]}]},
        ]
        payload = {'collection_id': str(self.a.id), 'title': 'Mein bearbeiteter Titel', 'body_json': nodes}
        with TestClient(app) as client:
            invalid = client.post('/api/notes', json=payload)
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(invalid.json()['error']['message'], 'Request validation failed')
            self.assertEqual(invalid.json()['error']['details'][0]['loc'], ['body', 'body_json'])
            document = {'type': 'doc', 'content': nodes}
            payload['body_json'] = document
            result = client.post('/api/notes', json=payload)
            self.assertEqual(result.status_code, 201, result.text)
            self.assertEqual(result.json()['title'], payload['title'])
            self.assertEqual(result.json()['body_json'], document)
            stored = NoteService(self.db, self.owner).get_note(uuid.UUID(result.json()['id']))
            self.assertIn('Nächste Schritte', stored.body_text)
            self.assertIn('Mein ergänzter Gedanke', stored.body_text)
            self.assertEqual(stored.collection_id, self.a.id)
        self.db.refresh(original)
        self.assertEqual(original.text, 'Originaler Gedanke bleibt erhalten')
        self.assertEqual(original.status, 'open')

    def test_group_move_is_atomic_and_owner_scoped(self):
        first = self.create(content='Eins')
        second = self.create(content='Zwei')
        payload = PinPositionBatchRequest(room_id=first.room_id, items=[
            PinPositionItem(id=first.id, position_x=100, position_y=200, base_updated_at=first.updated_at),
            PinPositionItem(id=second.id, position_x=400, position_y=250, base_updated_at=second.updated_at)])
        self.assertEqual(len(self.service.move_many(payload)), 2)
        self.assertEqual((first.position_x,second.position_x), (100,400))
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).move_many(payload)
        payload.items[0].position_x = 900
        payload.items[0].base_updated_at = first.updated_at
        payload.items[1].base_updated_at = second.created_at
        with self.assertRaises(ConflictError):
            self.service.move_many(payload)
        self.assertEqual((first.position_x,second.position_x), (100,400))
        with self.assertRaises(ValidationError):
            PinPositionBatchRequest(room_id=first.room_id, items=[payload.items[0],payload.items[0]])

    def test_bulk_color_validates_whole_selection_before_updating(self):
        first = self.create(content='Eins')
        second = self.create(content='Zwei')
        third = self.create(content='Drei')
        payload = PinColorBatchRequest(room_id=first.room_id, ids=[first.id, second.id], title_color='#cbdff1', base_updated_at={first.id:first.updated_at, second.id:second.updated_at})
        self.assertEqual(len(self.service.color_many(payload)), 2)
        self.assertEqual(first.title_color, '#cbdff1')
        self.assertEqual(second.title_color, '#cbdff1')
        self.assertIsNone(third.title_color)
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).color_many(payload)
        payload.ids = [first.id, third.id]
        payload.title_color = '#efd2dc'
        payload.base_updated_at = {first.id:first.created_at, third.id:third.updated_at}
        with self.assertRaises(ConflictError):
            self.service.color_many(payload)
        self.assertIsNone(third.title_color)

    def test_room_deletion_is_owned_and_removes_only_its_pins(self):
        room = self.service.create_room(self.a.id, 'Löschen')
        other_room = self.service.create_room(self.a.id, 'Bleibt')
        self.service.create(PinCreateRequest(collection_id=self.a.id, room_id=room.id, text='Entfernen'))
        keep = self.service.create(PinCreateRequest(collection_id=self.a.id, room_id=other_room.id, text='Bleibt'))
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).delete_room(room.id)
        self.service.delete_room(room.id)
        self.assertEqual([p.id for p in self.service.list(self.a.id)], [keep.id])
        self.assertEqual([r.id for r in self.service.rooms(self.a.id)], [other_room.id])
        self.service.delete_room(other_room.id)
        self.assertEqual(self.service.rooms(self.a.id), [])

    def test_automatic_room_names_follow_existing_numbered_rooms(self):
        self.assertEqual(self.service.create_room(self.a.id).title, 'Sammlung 1')
        self.service.create_room(self.a.id, 'Fläche 4')
        self.service.create_room(self.a.id, 'Projekt')
        self.assertEqual(self.service.create_room(self.a.id).title, 'Sammlung 5')
        self.assertEqual(self.service.create_room(self.b.id).title, 'Sammlung 1')

    def test_rooms_keep_canvases_separate_and_owned(self):
        first = self.service.ensure_room(self.a.id)
        second = self.service.create_room(self.a.id, 'Ideen')
        pin = self.service.create(PinCreateRequest(collection_id=self.a.id, room_id=second.id, text='Im zweiten Raum'))
        self.assertEqual(pin.room_id, second.id)
        self.assertEqual(self.service.list(self.a.id, room_id=first.id), [])
        self.assertEqual([p.id for p in self.service.list(self.a.id, room_id=second.id)], [pin.id])
        self.assertEqual(self.service.rename_room(second.id, 'Projekt').title, 'Projekt')
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).rename_room(second.id, 'Fremd')
        with self.assertRaises(NotFoundError):
            self.service.create(PinCreateRequest(collection_id=self.b.id, room_id=second.id, text='Falsche Sammlung'))

    def test_title_color_persists_without_text_update_reset(self):
        pin = self.create()
        updated = self.service.update(pin.id, PinUpdateRequest(text=pin.text, title_color='#334455', base_updated_at=pin.updated_at))
        self.assertEqual(PinRead.model_validate(updated).title_color, '#334455')
        updated = self.service.update(pin.id, PinUpdateRequest(text='Neuer Text', base_updated_at=updated.updated_at))
        self.assertEqual(updated.title_color, '#334455')
        with self.assertRaises(ValidationError):
            PinUpdateRequest(text='Text', title_color='red', base_updated_at=updated.updated_at)
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).update(pin.id, PinUpdateRequest(text='Text', title_color='#112233', base_updated_at=updated.updated_at))

    def test_text_tags_scoping_and_count(self):
        pin = self.create(content='  Ein Gedanke\n#Übergabe #übergabe')
        self.assertEqual(pin.text, '  Ein Gedanke\n#Übergabe #übergabe')
        self.assertEqual([t.name for t in pin.tags], ['Übergabe'])
        self.assertEqual(PinRead.model_validate(pin).collection_id, self.a.id)
        self.create(self.b.id)
        self.assertEqual([p.id for p in self.service.list(self.a.id)], [pin.id])
        self.assertEqual(self.service.count(self.a.id), 1)
        with self.assertRaises(NotFoundError):
            self.create(self.other_collection)
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).list(self.a.id)

    def test_edit_conflict_and_tag_replacement(self):
        pin = self.create()
        original = pin.updated_at
        updated = self.service.update(pin.id, PinUpdateRequest(text='Neu #Projekt', base_updated_at=original))
        self.assertEqual([t.name for t in updated.tags], ['Projekt'])
        with self.assertRaises(ConflictError):
            self.service.update(pin.id, PinUpdateRequest(text='Veraltet', base_updated_at=original))
        self.db.rollback()
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).update(pin.id, PinUpdateRequest(text='Fremd', base_updated_at=updated.updated_at))

    def test_archive_restore_and_foreign_ids(self):
        a, b = self.create(), self.create(self.b.id)
        self.assertEqual(self.service.archive(self.a.id, [a.id, b.id]), 1)
        self.assertEqual(self.service.count(self.a.id), 0)
        self.assertEqual(self.service.list(self.a.id, archived=True)[0].text, a.text)
        self.assertEqual(self.service.archive(self.a.id, [a.id], False), 1)
        self.assertEqual(self.service.count(self.a.id), 1)

    def test_collection_delete_requires_target_and_moves_thoughts(self):
        pin = self.create()
        self.service.archive(self.a.id, [pin.id])
        with self.assertRaises(ConflictError):
            self.collections.delete_collection(self.a.id)
        self.collections.delete_collection(self.a.id, reassign_to=self.b.id)
        self.assertEqual(self.service.list(self.b.id, archived=True)[0].id, pin.id)

    def test_unpositioned_thoughts_get_distinct_free_slots(self):
        with self.assertRaises(ValidationError):
            PinCreateRequest(collection_id=self.a.id, text="Halb", position_x=5)
        taken = self.service.create(PinCreateRequest(collection_id=self.a.id, text="Fest", position_x=24, position_y=24))
        first = self.service.create(PinCreateRequest(collection_id=self.a.id, text="Schnell 1"))
        second = self.service.create(PinCreateRequest(collection_id=self.a.id, text="Schnell 2"))
        spots = {(p.position_x, p.position_y) for p in (taken, first, second)}
        self.assertEqual(len(spots), 3)
        self.assertNotIn(None, [p.position_x for p in (first, second)])

    def test_position_survives_reload_and_move_is_owner_scoped(self):
        pin = self.service.create(PinCreateRequest(collection_id=self.a.id, text="Hier", position_x=137, position_y=281))
        original = pin.updated_at
        moved = self.service.move(pin.id, PinPositionRequest(position_x=403, position_y=519, base_updated_at=original))
        self.db.expire_all()
        saved = self.service.list(self.a.id)[0]
        self.assertEqual((saved.position_x, saved.position_y), (403, 519))
        self.assertEqual(saved.text, "Hier")
        with self.assertRaises(ConflictError):
            self.service.move(pin.id, PinPositionRequest(position_x=1, position_y=2, base_updated_at=original))
        self.db.rollback()
        with self.assertRaises(NotFoundError):
            NotePinService(self.db, self.other).move(pin.id, PinPositionRequest(position_x=0, position_y=0, base_updated_at=moved.updated_at))
        with self.assertRaises(ValidationError):
            PinPositionRequest(position_x=-1, position_y=0, base_updated_at=moved.updated_at)

    def test_creation_retry_does_not_duplicate_a_positioned_thought(self):
        payload = PinCreateRequest(request_id=uuid.uuid4(), collection_id=self.a.id, text="Einmal", position_x=11, position_y=22)
        first = self.service.create(payload)
        second = self.service.create(payload)
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.service.count(self.a.id), 1)

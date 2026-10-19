import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, MetaData, Table, Uuid, create_engine, select
from sqlalchemy.orm import Session

from app.services.note_service import NoteService
from app.worker import main as worker_main


class NoteTrashRetentionTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
        self.owner = uuid4()
        self.other_owner = uuid4()
        self.engine = create_engine("sqlite://")
        self.table = Table(
            "note", MetaData(),
            Column("id", Uuid(), primary_key=True),
            Column("owner_id", Uuid(), nullable=False),
            Column("is_deleted", Boolean(), nullable=False),
            Column("deleted_at", DateTime(timezone=True)),
        )
        self.table.create(self.engine)
        self.rows = [
            dict(id=uuid4(), owner_id=self.owner, is_deleted=True, deleted_at=self.now - timedelta(days=45)),
            dict(id=uuid4(), owner_id=self.owner, is_deleted=True, deleted_at=self.now - timedelta(days=30)),
            dict(id=uuid4(), owner_id=self.owner, is_deleted=True, deleted_at=self.now - timedelta(days=29)),
            dict(id=uuid4(), owner_id=self.owner, is_deleted=False, deleted_at=self.now - timedelta(days=45)),
            dict(id=uuid4(), owner_id=self.other_owner, is_deleted=True, deleted_at=self.now - timedelta(days=40)),
            dict(id=uuid4(), owner_id=self.owner, is_deleted=True, deleted_at=None),
        ]
        self.db = Session(self.engine)
        self.db.execute(self.table.insert(), self.rows)
        self.db.commit()
        self.clock = mock.patch("app.services.note_service.datetime")
        self.clock.start().now.return_value = self.now
        self.addCleanup(self.clock.stop)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def delete_selected_note(self, service, note_id, *, deleted_before):
        row = next(row for row in self.rows if row["id"] == note_id)
        self.assertEqual(service.owner_id, row["owner_id"])
        self.assertEqual(deleted_before, self.now - timedelta(days=30))
        self.db.execute(self.table.delete().where(self.table.c.id == note_id))
        self.db.commit()
        return True

    def remaining_ids(self):
        return set(self.db.scalars(select(self.table.c.id)))

    def test_only_expired_notes_of_the_requested_owner_are_deleted(self):
        with mock.patch.object(NoteService, "delete_note", autospec=True, side_effect=self.delete_selected_note):
            self.assertEqual(NoteService(self.db, self.owner).purge_expired_trash(30), 2)
        self.assertEqual(self.remaining_ids(), {row["id"] for row in self.rows[2:]})

    def test_worker_cleans_expired_notes_across_owners(self):
        with mock.patch.object(NoteService, "delete_note", autospec=True, side_effect=self.delete_selected_note):
            self.assertEqual(NoteService(self.db).purge_expired_trash(30), 3)
        self.assertEqual(self.remaining_ids(), {self.rows[index]["id"] for index in [2, 3, 5]})

    def test_never_does_not_query_or_delete_notes(self):
        db = mock.Mock()
        self.assertEqual(NoteService(db).purge_expired_trash(0), 0)
        db.execute.assert_not_called()
        db.delete.assert_not_called()

    def test_one_failed_deletion_does_not_stop_the_other_notes(self):
        def delete(service, note_id, **kwargs):
            if note_id == self.rows[0]["id"]:
                raise RuntimeError("simulated failure")
            return self.delete_selected_note(service, note_id, **kwargs)

        with mock.patch.object(NoteService, "delete_note", autospec=True, side_effect=delete):
            with self.assertLogs("app.services.note_service", level="ERROR"):
                self.assertEqual(NoteService(self.db, self.owner).purge_expired_trash(30), 1)
        self.assertIn(self.rows[0]["id"], self.remaining_ids())
        self.assertNotIn(self.rows[1]["id"], self.remaining_ids())

    def test_expiration_is_rechecked_under_lock_before_deleting(self):
        cutoff = self.now - timedelta(days=30)
        for is_deleted, deleted_at in [
            (False, self.now - timedelta(days=45)),
            (True, self.now - timedelta(days=1)),
            (True, None),
        ]:
            with self.subTest(is_deleted=is_deleted, deleted_at=deleted_at):
                db = mock.Mock()
                note = SimpleNamespace(id=uuid4(), is_deleted=is_deleted, deleted_at=deleted_at)
                service = NoteService(db, self.owner)
                service._get = mock.Mock(return_value=note)
                self.assertFalse(service.delete_note(note.id, deleted_before=cutoff))
                service._get.assert_called_once_with(note.id, include_deleted=True, for_update=True)
                db.delete.assert_not_called()
                db.commit.assert_not_called()

    def test_expired_note_deletion_also_removes_its_images(self):
        db = mock.Mock()
        db.scalars.return_value.all.return_value = ["note-images/expired.png"]
        note = SimpleNamespace(id=uuid4(), is_deleted=True, deleted_at=self.now - timedelta(days=45))
        service = NoteService(db, self.owner)
        service._get = mock.Mock(return_value=note)
        with mock.patch("app.services.note_service.NoteImageStorage") as storage:
            self.assertTrue(service.delete_note(note.id, deleted_before=self.now - timedelta(days=30)))
            storage.return_value.cleanup.assert_called_once_with("note-images/expired.png")
        db.delete.assert_called_once_with(note)
        db.commit.assert_called_once()


class WorkerTrashRetentionTest(unittest.TestCase):
    def test_worker_applies_the_setting_to_documents_and_notes_and_respects_never(self):
        for days in [0, 7, 365]:
            with self.subTest(days=days):
                runtime = SimpleNamespace(documents=SimpleNamespace(trash_retention_days=days))
                with mock.patch.object(worker_main, "SessionLocal"):
                    with mock.patch.object(worker_main, "SettingsService") as settings_service:
                        with mock.patch.object(worker_main, "DocumentService") as documents:
                            with mock.patch.object(worker_main, "NoteService") as notes:
                                settings_service.return_value.get_settings.return_value = runtime
                                documents.return_value.purge_expired_trash.return_value = 1
                                notes.return_value.purge_expired_trash.return_value = 2
                                worker_main._cleanup_expired_trash()
                                if days == 0:
                                    documents.assert_not_called()
                                    notes.assert_not_called()
                                else:
                                    documents.return_value.purge_expired_trash.assert_called_once_with(days)
                                    notes.return_value.purge_expired_trash.assert_called_once_with(days)

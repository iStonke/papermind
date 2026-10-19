"""Synthetic uploads in the isolated test database; no user documents involved."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import select, delete

from app.db.session import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.schemas.import_staging import ImportCommitRequest
from app.services import import_staging
from app.services.import_staging import ImportStagingService
from tests.test_scanner_scan_job_lifecycle import _schema_ready


@unittest.skipUnless(_schema_ready(), 'Isolated PostgreSQL schema required')
class ImportCommitIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old_storage = import_staging.settings.storage_path
        import_staging.settings.storage_path = self.directory.name
        self.db = SessionLocal()
        self.user = User(username=f'import-test-{uuid.uuid4().hex}', password_hash='test', is_active=True, is_admin=False)
        self.db.add(self.user)
        self.db.commit()
        self.service = ImportStagingService(self.db, self.user.id)
        self.source_id = str(uuid.uuid4())
        self.service._authorized_sources.add(self.source_id)
        source = self.service._source_pdf_path(self.source_id)
        source.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (120, 160), 'white').save(source, format='PDF', resolution=100)
        source.with_suffix('.owner.json').write_text(json.dumps({'owner_id': str(self.user.id)}))
        self.request = ImportCommitRequest.model_validate({'request_id': str(uuid.uuid4()), 'options': {'auto_ocr': False},
            'documents': [{'client_document_id': 'draft-1', 'title': 'Synthetischer Import', 'document_type': 'Brief', 'tag_names': ['Synthetisches Tag'],
                'pages': [{'source_file_id': self.source_id, 'page_index': 0}]}]})

    def tearDown(self):
        self.db.rollback()
        self.db.execute(delete(Document).where(Document.owner_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()
        import_staging.settings.storage_path = self.old_storage
        self.directory.cleanup()

    def test_lost_response_replays_receipt_after_source_cleanup(self):
        first = self.service.commit(self.request)
        self.assertFalse(first.errors, first.errors)
        second = self.service.commit(self.request)
        self.assertFalse(second.errors, second.errors)
        self.assertEqual(first.created[0].doc_id, second.created[0].doc_id)
        self.assertTrue(second.created[0].replayed)
        docs = self.db.scalars(select(Document).where(Document.owner_id == self.user.id)).all()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].document_type, 'Brief')
        self.assertIsNone(docs[0].document_date)
        self.assertEqual([tag.name for tag in docs[0].tags], ['Synthetisches Tag'])

    def test_metadata_failure_rolls_back_the_document_and_preserves_source(self):
        original_finalize = self.service.document_service.upload_document
        def failing_upload(*args, **kwargs):
            kwargs['finalize_import'] = lambda document: (_ for _ in ()).throw(RuntimeError('synthetic metadata failure'))
            return original_finalize(*args, **kwargs)
        with patch.object(self.service.document_service, 'upload_document', side_effect=failing_upload):
            response = self.service.commit(self.request)
        self.assertFalse(response.created)
        self.assertTrue(response.errors)
        self.assertFalse(self.db.scalars(select(Document).where(Document.owner_id == self.user.id)).all())
        self.assertTrue(self.service._source_pdf_path(self.source_id).exists())

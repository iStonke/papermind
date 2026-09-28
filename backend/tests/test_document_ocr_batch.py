import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.documents import DocumentService


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self.values


def _document(*, status="not_started", original=True, deleted=False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        is_deleted=deleted,
        ocr_status=status,
        files=[SimpleNamespace(role="original")] if original else [],
    )


class DocumentOcrBatchTest(unittest.TestCase):
    def test_safe_preview_only_counts_missing_or_failed_ocr(self) -> None:
        pending = _document()
        completed = _document(status="done")
        active = _document(status="running")
        missing_file = _document(status="failed", original=False)
        deleted = _document(deleted=True)
        unavailable_id = uuid.uuid4()

        db = MagicMock()
        db.execute.side_effect = [
            _ScalarResult([pending, completed, active, missing_file, deleted]),
            _ScalarResult([active.id]),
        ]
        service = DocumentService(db)
        service._queue_ocr_job = MagicMock()

        result = service.queue_ocr_for_documents(
            [pending.id, completed.id, active.id, missing_file.id, deleted.id, unavailable_id],
            dry_run=True,
        )

        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["queued"], 0)
        self.assertEqual(result["skipped_completed"], 1)
        self.assertEqual(result["skipped_active"], 1)
        self.assertEqual(result["skipped_missing_file"], 1)
        self.assertEqual(result["skipped_deleted_or_unavailable"], 2)
        service._queue_ocr_job.assert_not_called()
        db.commit.assert_not_called()

    def test_explicit_rerun_queues_completed_documents(self) -> None:
        completed = _document(status="done")
        db = MagicMock()
        db.execute.side_effect = [
            _ScalarResult([completed]),
            _ScalarResult([]),
        ]
        service = DocumentService(db)
        service._queue_ocr_job = MagicMock()

        result = service.queue_ocr_for_documents(
            [completed.id],
            rerun_completed=True,
        )

        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["queued"], 1)
        self.assertEqual(result["queued_document_ids"], [str(completed.id)])
        service._queue_ocr_job.assert_called_once_with(completed)
        db.commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
from unittest.mock import Mock

from app.services.job_queue import enqueue_document_job


class JobQueueTest(unittest.TestCase):
    def test_enqueue_adds_a_queued_job_when_none_is_active(self) -> None:
        db = Mock()
        db.execute.return_value.scalar_one_or_none.return_value = None
        document_id = uuid.uuid4()

        job = enqueue_document_job(db, document_id, "INDEX")

        self.assertIsNotNone(job)
        self.assertEqual(job.document_id, document_id)
        self.assertEqual(job.type, "INDEX")
        self.assertEqual(job.status, "queued")
        db.add.assert_called_once_with(job)

    def test_enqueue_does_not_add_duplicate_active_job(self) -> None:
        db = Mock()
        db.execute.return_value.scalar_one_or_none.return_value = uuid.uuid4()

        job = enqueue_document_job(db, uuid.uuid4(), "TAG")

        self.assertIsNone(job)
        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()

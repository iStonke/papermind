import unittest
import uuid
from unittest.mock import Mock

from app.services.tags import TagService


class TagCleanupServiceTest(unittest.TestCase):
    def test_cleanup_orphan_tags_skips_when_candidate_set_is_empty(self) -> None:
        db = Mock()

        deleted_count = TagService.cleanup_orphan_tags(db, candidate_tag_ids=set())

        self.assertEqual(deleted_count, 0)
        db.execute.assert_not_called()

    def test_cleanup_orphan_tags_executes_delete_for_candidates(self) -> None:
        db = Mock()
        db.execute.return_value = Mock(rowcount=2)

        deleted_count = TagService.cleanup_orphan_tags(db, candidate_tag_ids={uuid.uuid4(), uuid.uuid4()})

        self.assertEqual(deleted_count, 2)
        db.execute.assert_called_once()

    def test_cleanup_orphan_tags_executes_global_cleanup_when_candidates_not_provided(self) -> None:
        db = Mock()
        db.execute.return_value = Mock(rowcount=1)

        deleted_count = TagService.cleanup_orphan_tags(db)

        self.assertEqual(deleted_count, 1)
        db.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
from unittest.mock import Mock, patch

from app.core.errors import ConflictError
from app.services.tags import TagService
from app.schemas.tags import TagCreateRequest, TagUpdateRequest


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

    def test_list_tags_does_not_auto_delete_unassigned_tags(self) -> None:
        db = Mock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        service = TagService(db)

        with patch.object(TagService, "cleanup_orphan_tags") as cleanup:
            result = service.list_tags(include_count=False)

        self.assertEqual(result, [])
        cleanup.assert_not_called()

    def test_create_tag_returns_existing_case_insensitive_duplicate(self) -> None:
        existing = Mock(id=uuid.uuid4(), name="Rechnung")
        db = Mock()
        db.execute.return_value.scalar_one_or_none.return_value = existing
        service = TagService(db)

        result = service.create_tag(TagCreateRequest(name="rechnung"))

        self.assertIs(result, existing)
        db.add.assert_not_called()

    def test_update_tag_rejects_case_insensitive_duplicate(self) -> None:
        tag_id = uuid.uuid4()
        existing_tag = Mock(id=tag_id, name="Rechnung")
        db = Mock()
        db.get.return_value = existing_tag
        db.execute.return_value.scalar_one_or_none.return_value = object()
        service = TagService(db)

        with self.assertRaises(ConflictError):
            service.update_tag(tag_id, TagUpdateRequest(name="rechnung"))

        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.errors import BadRequestError, ConflictError
from app.models.correspondent import CorrespondentAlias
from app.schemas.correspondents import CorrespondentCreateRequest
from app.services.correspondents import CorrespondentService


class CorrespondentHierarchyValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CorrespondentService(MagicMock())

    def test_collection_without_parent_is_allowed(self) -> None:
        self.service._validate_hierarchy(entity_id=None, kind="collection", parent_id=None)

    def test_person_can_be_assigned_to_organization(self) -> None:
        self.service._get_owned = MagicMock(return_value=SimpleNamespace(kind="organization"))
        self.service._has_children = MagicMock(return_value=False)
        self.service._validate_hierarchy(
            entity_id=uuid.uuid4(),
            kind="person",
            parent_id=uuid.uuid4(),
        )

    def test_collection_cannot_have_parent(self) -> None:
        with self.assertRaisesRegex(BadRequestError, "Nur Personen"):
            self.service._validate_hierarchy(
                entity_id=uuid.uuid4(),
                kind="collection",
                parent_id=uuid.uuid4(),
            )

    def test_organization_with_persons_cannot_change_type(self) -> None:
        self.service._has_children = MagicMock(return_value=True)
        with self.assertRaisesRegex(BadRequestError, "Typ kann nicht geändert werden"):
            self.service._validate_hierarchy(
                entity_id=uuid.uuid4(),
                kind="collection",
                parent_id=None,
            )


class CorrespondentAliasDeletionTest(unittest.TestCase):
    def test_deleting_alias_also_deletes_automatic_matchers(self) -> None:
        db = MagicMock()
        service = CorrespondentService(db)
        correspondent_id = uuid.uuid4()
        alias_id = uuid.uuid4()
        alias = CorrespondentAlias(id=alias_id, correspondent_id=correspondent_id, alias="ING")
        matcher_a = SimpleNamespace(pattern="ING")
        matcher_b = SimpleNamespace(pattern="ing")

        service.get_correspondent_or_404 = MagicMock(return_value=SimpleNamespace(id=correspondent_id))
        db.get.return_value = alias
        db.execute.return_value.scalars.return_value.all.return_value = [matcher_a, matcher_b]

        service.delete_alias(correspondent_id, alias_id)

        db.delete.assert_any_call(matcher_a)
        db.delete.assert_any_call(matcher_b)
        db.delete.assert_any_call(alias)
        db.commit.assert_called_once()


class CorrespondentDocumentUnlinkTest(unittest.TestCase):
    def test_unlink_documents_clears_all_owned_assignments(self) -> None:
        db = MagicMock()
        db.execute.return_value.rowcount = 3
        owner_id = uuid.uuid4()
        correspondent_id = uuid.uuid4()
        service = CorrespondentService(db, owner_id)
        service.get_correspondent_or_404 = MagicMock(
            return_value=SimpleNamespace(id=correspondent_id)
        )

        count = service.unlink_documents(correspondent_id)

        self.assertEqual(count, 3)
        db.execute.assert_called_once()
        db.commit.assert_called_once()


class CorrespondentAliasConflictTest(unittest.TestCase):
    def test_alias_cannot_belong_to_two_correspondents(self) -> None:
        db = MagicMock()
        service = CorrespondentService(db, uuid.uuid4())
        correspondent_id = uuid.uuid4()
        conflicting_alias = CorrespondentAlias(
            id=uuid.uuid4(),
            correspondent_id=uuid.uuid4(),
            alias="ING",
        )

        service.get_correspondent_or_404 = MagicMock(return_value=SimpleNamespace(id=correspondent_id))
        service._find_name_conflict = MagicMock(return_value=None)
        service._find_alias_conflict = MagicMock(return_value=conflicting_alias)

        with self.assertRaisesRegex(ConflictError, "bereits einem anderen Korrespondenten"):
            service.add_alias(correspondent_id, "ING")

        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_alias_cannot_duplicate_another_correspondent_name(self) -> None:
        db = MagicMock()
        service = CorrespondentService(db, uuid.uuid4())
        correspondent_id = uuid.uuid4()
        service.get_correspondent_or_404 = MagicMock(return_value=SimpleNamespace(id=correspondent_id))
        service._find_name_conflict = MagicMock(
            return_value=SimpleNamespace(id=uuid.uuid4(), name="ING")
        )

        with self.assertRaisesRegex(ConflictError, "Korrespondentenname"):
            service.add_alias(correspondent_id, "ING")

    def test_correspondent_name_cannot_duplicate_an_alias(self) -> None:
        db = MagicMock()
        service = CorrespondentService(db, uuid.uuid4())
        service._find_name_conflict = MagicMock(return_value=None)
        service._find_alias_conflict = MagicMock(
            return_value=CorrespondentAlias(
                id=uuid.uuid4(),
                correspondent_id=uuid.uuid4(),
                alias="ING",
            )
        )

        with self.assertRaisesRegex(ConflictError, "Alias oder Erkennungsname"):
            service.create_correspondent(
                CorrespondentCreateRequest(name="ING", kind="organization")
            )

        db.add.assert_not_called()


if __name__ == "__main__":
    unittest.main()

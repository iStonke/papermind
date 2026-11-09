import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.errors import BadRequestError, ConflictError
from app.models.correspondent import Correspondent, CorrespondentAlias
from app.schemas.correspondents import CorrespondentCreateRequest, CorrespondentUpdateRequest
from app.services.correspondents import CorrespondentService


class CorrespondentHierarchyValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CorrespondentService(MagicMock())

    def test_collection_without_parent_is_allowed(self) -> None:
        self.service._validate_hierarchy(entity_id=None, kind="collection", parent_id=None)

    def test_person_can_be_assigned_to_organization(self) -> None:
        self.service._get_owned = MagicMock(return_value=SimpleNamespace(kind="organization"))
        self.service._child_kinds = MagicMock(return_value=set())
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

    def test_organization_with_persons_cannot_become_a_person(self) -> None:
        self.service._child_kinds = MagicMock(return_value={"person"})
        with self.assertRaisesRegex(BadRequestError, "Typ kann nicht geändert werden"):
            self.service._validate_hierarchy(
                entity_id=uuid.uuid4(),
                kind="person",
                parent_id=None,
            )

    def test_organization_with_persons_can_become_a_collection(self) -> None:
        self.service._child_kinds = MagicMock(return_value={"person"})
        self.service._validate_hierarchy(entity_id=uuid.uuid4(), kind="collection", parent_id=None)

    def test_collection_with_organizations_cannot_become_an_organization(self) -> None:
        self.service._child_kinds = MagicMock(return_value={"organization", "person"})
        with self.assertRaisesRegex(BadRequestError, "Typ kann nicht geändert werden"):
            self.service._validate_hierarchy(entity_id=uuid.uuid4(), kind="organization", parent_id=None)

    def test_organization_can_join_a_collection(self) -> None:
        self.service._get_owned = MagicMock(return_value=SimpleNamespace(kind="collection"))
        self.service._child_kinds = MagicMock(return_value={"person"})
        self.service._validate_hierarchy(entity_id=uuid.uuid4(), kind="organization", parent_id=uuid.uuid4())

    def test_person_can_join_a_collection(self) -> None:
        self.service._get_owned = MagicMock(return_value=SimpleNamespace(kind="collection"))
        self.service._child_kinds = MagicMock(return_value=set())
        self.service._validate_hierarchy(entity_id=uuid.uuid4(), kind="person", parent_id=uuid.uuid4())

    def test_organization_cannot_join_an_organization(self) -> None:
        self.service._get_owned = MagicMock(return_value=SimpleNamespace(kind="organization"))
        with self.assertRaisesRegex(BadRequestError, "Organisationen zu einer Sammlung"):
            self.service._validate_hierarchy(entity_id=uuid.uuid4(), kind="organization", parent_id=uuid.uuid4())


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


class CorrespondentRelationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()
        self.service = CorrespondentService(self.db)
        self.me = SimpleNamespace(id=uuid.uuid4(), owner_id=uuid.uuid4(), name="Vodafone", kind="organization")
        self.other = SimpleNamespace(id=uuid.uuid4(), owner_id=self.me.owner_id, name="Kabel Deutschland", kind="organization")
        self.service.get_correspondent_or_404 = MagicMock(return_value=self.me)
        self.service._get_owned = MagicMock(return_value=self.other)

    def _request(self, role: str):
        from app.schemas.correspondents import CorrespondentRelationCreateRequest

        return CorrespondentRelationCreateRequest(role=role, other_id=self.other.id)

    def test_roles_are_read_from_the_profile_perspective(self) -> None:
        from app.models.correspondent import CorrespondentRelation

        edge = CorrespondentRelation(kind="successor", source_id=self.other.id, target_id=self.me.id)
        self.assertEqual(CorrespondentService._role_of(edge, self.me.id), "predecessor")
        self.assertEqual(CorrespondentService._role_of(edge, self.other.id), "successor")
        agent = CorrespondentRelation(kind="acts_for", source_id=self.other.id, target_id=self.me.id)
        self.assertEqual(CorrespondentService._role_of(agent, self.me.id), "agent")
        self.assertEqual(CorrespondentService._role_of(agent, self.other.id), "acts_for")

    def test_predecessor_with_existing_successor_is_rejected(self) -> None:
        self.service._get_successor_id = MagicMock(return_value=uuid.uuid4())
        with self.assertRaisesRegex(ConflictError, "bereits einen Nachfolger"):
            self.service.add_relation(self.me.id, self._request("predecessor"))
        self.service._get_successor_id.assert_called_once_with(self.other.id)

    def test_successor_cycle_is_rejected(self) -> None:
        self.service._get_successor_id = MagicMock(return_value=None)
        # Der gewünschte Nachfolger stammt bereits von diesem Korrespondenten ab.
        self.service._successor_chain = MagicMock(return_value={self.other.id, self.me.id})
        with self.assertRaisesRegex(BadRequestError, "Kreis"):
            self.service.add_relation(self.me.id, self._request("successor"))

    def test_new_relations_require_a_person_or_organization_at_both_ends(self) -> None:
        for kinds in [("collection", "person"), ("person", "collection"), (None, "person"), ("person", None)]:
            self.me.kind, self.other.kind = kinds
            for role in ("successor", "acts_for"):
                with self.subTest(kinds=kinds, role=role):
                    with self.assertRaisesRegex(BadRequestError, "nur zwischen Personen und Organisationen"):
                        self.service.add_relation(self.me.id, self._request(role))
        self.db.add.assert_not_called()

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._request("friend")


class CorrespondentPersonNameTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()
        self.service = CorrespondentService(self.db, uuid.uuid4())
        self.person = Correspondent(id=uuid.uuid4(), name="Jan van Berg", kind="person")
        self.service.get_correspondent_or_404 = MagicMock(return_value=self.person)
        self.service._find_name_conflict = MagicMock(return_value=None)
        self.service._find_alias_conflict = MagicMock(return_value=None)

    def test_create_derives_name_and_keeps_name_parts(self) -> None:
        person = self.service.create_correspondent(CorrespondentCreateRequest(
            name="Jan van Berg", kind="person", first_name="  Jan   Erik ", last_name="van Berg",
        ))
        self.assertEqual((person.name, person.first_name, person.last_name), ("Jan Erik van Berg", "Jan Erik", "van Berg"))

    def test_create_derives_short_name_without_legal_form(self) -> None:
        created = self.service.create_correspondent(CorrespondentCreateRequest(name="Vodafone GmbH", kind="organization"))
        self.assertEqual((created.name, created.short_name), ("Vodafone GmbH", "Vodafone"))
        untyped = self.service.create_correspondent(CorrespondentCreateRequest(name="Wiker Autoservice GmbH & Co. KG"))
        self.assertEqual(untyped.short_name, "Wiker Autoservice")
        plain = self.service.create_correspondent(CorrespondentCreateRequest(name="Finanzamt Kiel", kind="organization"))
        self.assertIsNone(plain.short_name)

    def test_explicit_short_name_or_null_wins_over_legal_form_default(self) -> None:
        kept = self.service.create_correspondent(CorrespondentCreateRequest(name="Vodafone GmbH", kind="organization", short_name=None))
        self.assertIsNone(kept.short_name)
        custom = self.service.create_correspondent(CorrespondentCreateRequest(name="Vodafone GmbH", short_name="Vodafone DE"))
        self.assertEqual(custom.short_name, "Vodafone DE")
        collection = self.service.create_correspondent(CorrespondentCreateRequest(name="Stiftung GmbH", kind="collection"))
        self.assertIsNone(collection.short_name)

    def test_legacy_person_can_save_a_split_without_changing_the_display_name(self) -> None:
        self.service.update_correspondent(self.person.id, CorrespondentUpdateRequest(notes="Ansprechpartner"))
        self.assertIsNone(self.person.first_name)
        self.assertIsNone(self.person.last_name)
        self.service.update_correspondent(self.person.id, CorrespondentUpdateRequest(first_name="Jan", last_name="van Berg"))
        self.assertEqual((self.person.name, self.person.first_name, self.person.last_name), ("Jan van Berg", "Jan", "van Berg"))

    def test_partial_update_uses_the_stored_other_part(self) -> None:
        self.person.first_name = "Jan"
        self.person.last_name = "van Berg"
        self.service.update_correspondent(self.person.id, CorrespondentUpdateRequest(first_name="Jan Erik"))
        self.assertEqual((self.person.name, self.person.first_name, self.person.last_name), ("Jan Erik van Berg", "Jan Erik", "van Berg"))

    def test_legacy_rename_drops_the_stale_split(self) -> None:
        self.person.first_name = "Jan"
        self.person.last_name = "van Berg"
        self.service.update_correspondent(self.person.id, CorrespondentUpdateRequest(name="Jan Berg"))
        self.assertEqual(self.person.name, "Jan Berg")
        self.assertIsNone(self.person.first_name)
        self.assertIsNone(self.person.last_name)

    def test_name_parts_are_rejected_for_organizations(self) -> None:
        self.person.kind = "organization"
        with self.assertRaisesRegex(BadRequestError, "nur bei Personen"):
            self.service.update_correspondent(self.person.id, CorrespondentUpdateRequest(first_name="Jan", last_name="Berg"))
        self.db.commit.assert_not_called()

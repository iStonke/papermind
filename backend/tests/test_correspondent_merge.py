"""Zusammenführen zweier Korrespondenten in der isolierten Test-Datenbank."""
import unittest
import uuid

from sqlalchemy import delete, select

from app.core.errors import BadRequestError
from app.db.session import SessionLocal
from app.models.correspondent import Correspondent, CorrespondentAlias, CorrespondentMatcher, CorrespondentRelation
from app.models.document import Document
from app.models.note import Note, NoteLink
from app.models.note_collection import NoteCollection
from app.models.user import User
from app.services.correspondent_merge import _rewrite_note_links
from app.services.correspondents import CorrespondentService
from tests.test_scanner_scan_job_lifecycle import _schema_ready


class NoteLinkRewriteTest(unittest.TestCase):
    def test_only_correspondent_links_to_the_source_change(self) -> None:
        source, target, other = (str(uuid.uuid4()) for _ in range(3))
        body = {"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "wikiLink", "attrs": {"targetType": "correspondent", "targetId": source, "label": "Alt"}},
            {"type": "wikiLink", "attrs": {"targetType": "correspondent", "targetId": other}},
            {"type": "wikiLink", "attrs": {"targetType": "document", "targetId": source}},
        ]}]}
        self.assertTrue(_rewrite_note_links(body, source, target))
        links = body["content"][0]["content"]
        self.assertEqual([link["attrs"]["targetId"] for link in links], [target, other, source])
        self.assertFalse(_rewrite_note_links(body, source, target))


@unittest.skipUnless(_schema_ready(), "Isolated PostgreSQL schema required")
class CorrespondentMergeIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = User(username=f"merge-test-{uuid.uuid4().hex}", password_hash="test", is_active=True, is_admin=False)
        self.db.add(self.user)
        self.db.commit()
        self.service = CorrespondentService(self.db, self.user.id)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.execute(delete(Note).where(Note.owner_id == self.user.id))
        self.db.execute(delete(NoteCollection).where(NoteCollection.owner_id == self.user.id))
        self.db.execute(delete(Document).where(Document.owner_id == self.user.id))
        self.db.execute(delete(CorrespondentRelation).where(CorrespondentRelation.owner_id == self.user.id))
        self.db.execute(delete(Correspondent).where(Correspondent.owner_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _correspondent(self, name: str, **fields) -> Correspondent:
        correspondent = Correspondent(owner_id=self.user.id, name=name, **fields)
        self.db.add(correspondent)
        self.db.flush()
        return correspondent

    def _document(self, correspondent: Correspondent, **fields) -> Document:
        document = Document(owner_id=self.user.id, original_filename=f"{uuid.uuid4().hex}.pdf", correspondent_id=correspondent.id, **fields)
        self.db.add(document)
        return document

    def test_merge_moves_everything_and_keeps_the_old_name_as_alias(self) -> None:
        target = self._correspondent("Vodafone GmbH", kind="organization", notes="Vertrag 123")
        source = self._correspondent("Vodafone", kind="organization", short_name="VF", notes="Kundennr. 42")
        collection = self._correspondent("Telekommunikation", kind="collection")
        source.parent_id = collection.id
        person = self._correspondent("Erika Muster", kind="person", parent_id=source.id)
        agent = self._correspondent("Inkasso AG", kind="organization")
        self.db.add_all([
            CorrespondentAlias(correspondent_id=target.id, alias="Red Plus"),
            CorrespondentAlias(correspondent_id=source.id, alias="red plus"),
            CorrespondentAlias(correspondent_id=source.id, alias="Vodafone Kabel"),
            CorrespondentMatcher(correspondent_id=source.id, kind="contains", pattern="GigaKombi", scope="both", priority=100),
            CorrespondentRelation(owner_id=self.user.id, kind="acts_for", source_id=agent.id, target_id=source.id),
            CorrespondentRelation(owner_id=self.user.id, kind="successor", source_id=source.id, target_id=target.id),
        ])
        active = self._document(source)
        trashed = self._document(source, is_deleted=True)
        notes_collection = NoteCollection(owner_id=self.user.id, name="Test")
        self.db.add(notes_collection)
        self.db.flush()
        note = Note(owner_id=self.user.id, collection_id=notes_collection.id, title="Telefonat", body_json={"type": "doc", "content": [
            {"type": "wikiLink", "attrs": {"targetType": "correspondent", "targetId": str(source.id)}}]})
        self.db.add(note)
        self.db.flush()
        self.db.add(NoteLink(note_id=note.id, target_type="correspondent", target_id=source.id))
        self.db.commit()
        target_id, source_id = target.id, source.id

        merged, counts = self.service.merge_correspondents(target_id, source_id)

        self.assertIsNone(self.db.get(Correspondent, source_id))
        self.assertEqual((counts.documents, counts.members, counts.notes), (2, 1, 1))
        self.db.expire_all()
        self.assertEqual({self.db.get(Document, active.id).correspondent_id, self.db.get(Document, trashed.id).correspondent_id}, {target_id})
        self.assertEqual(self.db.get(Correspondent, person.id).parent_id, target_id)
        merged = self.db.get(Correspondent, target_id)
        self.assertEqual(merged.parent_id, collection.id)
        self.assertEqual(merged.short_name, "VF")
        self.assertEqual(merged.notes, "Vertrag 123\n\nAus „Vodafone“:\nKundennr. 42")
        aliases = sorted(alias.alias for alias in merged.aliases)
        self.assertEqual(aliases, ["Red Plus", "Vodafone", "Vodafone Kabel"])
        patterns = {matcher.pattern for matcher in merged.matchers}
        self.assertTrue({"GigaKombi", "Vodafone"} <= patterns)
        relations = self.db.execute(select(CorrespondentRelation).where(CorrespondentRelation.owner_id == self.user.id)).scalars().all()
        self.assertEqual([(r.kind, r.source_id, r.target_id) for r in relations], [("acts_for", agent.id, target_id)])
        note = self.db.get(Note, note.id)
        self.assertEqual(note.body_json["content"][0]["attrs"]["targetId"], str(target_id))
        self.assertEqual(note.revision, 2)
        links = self.db.execute(select(NoteLink.target_id).where(NoteLink.note_id == note.id)).scalars().all()
        self.assertEqual(links, [target_id])

    def test_untyped_source_can_join_a_typed_target(self) -> None:
        target = self._correspondent("Stadtwerke Kiel", kind="organization")
        source = self._correspondent("SW Kiel Netz")
        self.db.commit()
        merged, counts = self.service.merge_correspondents(target.id, source.id)
        self.assertEqual(merged.kind, "organization")
        self.assertEqual(counts.documents, 0)

    def test_untyped_target_adopts_the_source_kind(self) -> None:
        target = self._correspondent("Techem")
        source = self._correspondent("Techem GmbH", kind="organization")
        self.db.commit()
        merged, _ = self.service.merge_correspondents(target.id, source.id)
        self.assertEqual(merged.kind, "organization")

    def test_different_kinds_are_refused_without_changes(self) -> None:
        target = self._correspondent("Müller", kind="person")
        source = self._correspondent("Müller GmbH", kind="organization")
        self._document(source)
        self.db.commit()
        with self.assertRaisesRegex(BadRequestError, "gleichen Typs"):
            self.service.merge_correspondents(target.id, source.id)
        self.db.rollback()
        self.assertIsNotNone(self.db.get(Correspondent, source.id))

    def test_self_merge_is_refused(self) -> None:
        target = self._correspondent("Allein")
        self.db.commit()
        with self.assertRaises(BadRequestError):
            self.service.merge_correspondents(target.id, target.id)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_schema_ready(), "Isolated PostgreSQL schema required")
class CorrespondentRefinementIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        self.user = User(username=f"refine-test-{uuid.uuid4().hex}", password_hash="test", is_active=True, is_admin=False)
        self.db.add(self.user)
        self.db.commit()
        self.service = CorrespondentService(self.db, self.user.id)

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.execute(delete(Document).where(Document.owner_id == self.user.id))
        self.db.execute(delete(Correspondent).where(Correspondent.owner_id == self.user.id))
        self.db.execute(delete(User).where(User.id == self.user.id))
        self.db.commit()
        self.db.close()

    def _add(self, name: str, **fields) -> Correspondent:
        correspondent = Correspondent(owner_id=self.user.id, name=name, **fields)
        self.db.add(correspondent)
        self.db.flush()
        return correspondent

    def _document(self, text: str, **fields) -> Document:
        document = Document(owner_id=self.user.id, original_filename=f"{uuid.uuid4().hex}.pdf", text_content=text, **fields)
        self.db.add(document)
        self.db.commit()
        return document

    def test_collection_lists_all_members_with_mentioned_first(self) -> None:
        bank = self._add("Bank", kind="collection")
        sparkasse = self._add("Förde Sparkasse AöR", kind="organization", parent_id=bank.id)
        self._add("Volksbank", kind="organization", parent_id=bank.id)
        document = self._document("Förde Sparkasse\nKontoauszug Nr. 3")
        items = self.service.refinement_suggestions(bank.id, document.id)
        self.assertEqual([(item["name"], item["mentioned"]) for item in items], [("Förde Sparkasse AöR", True), ("Volksbank", False)])
        self.assertEqual(items[0]["id"], sparkasse.id)

    def test_organization_suggests_only_persons_named_in_the_letterhead(self) -> None:
        practice = self._add("Praxis am Markt", kind="organization")
        doctor = self._add("Anna Berger", kind="person", parent_id=practice.id, first_name="Anna", last_name="Berger")
        self._add("Tom Kühn", kind="person", parent_id=practice.id, first_name="Tom", last_name="Kühn")
        body = "Praxis am Markt\nDr. med. Berger\nRechnung\n" + "Leistungen " * 200 + "\nMit freundlichen Grüßen\nTom Kühn"
        items = self.service.refinement_suggestions(practice.id, self._document(body).id)
        self.assertEqual([item["id"] for item in items], [doctor.id])
        self.assertTrue(items[0]["mentioned"])

    def test_without_members_or_mentions_nothing_is_suggested(self) -> None:
        single = self._add("Techem", kind="organization")
        self.assertEqual(self.service.refinement_suggestions(single.id, self._document("Techem Abrechnung").id), [])

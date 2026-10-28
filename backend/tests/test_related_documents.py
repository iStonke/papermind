import unittest
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, MetaData, Table, Text, Uuid, create_engine
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.services.related_documents import RelatedDocumentService


class RelatedDocumentsTest(unittest.TestCase):
    """Execute real ranking/filter SQL against isolated, metadata-only tables."""
    def setUp(self):
        self.engine = create_engine('sqlite://')
        metadata = MetaData()
        self.documents = Table('documents', metadata,
            Column('id', Uuid, primary_key=True), Column('owner_id', Uuid),
            Column('original_filename', Text), Column('display_name', Text),
            Column('document_type', Text), Column('correspondent_id', Uuid),
            Column('is_deleted', Boolean), Column('document_date', Date), Column('created_at', DateTime))
        self.tags = Table('tags', metadata, Column('id', Uuid, primary_key=True), Column('owner_id', Uuid), Column('name', Text))
        self.links = Table('document_tags', metadata, Column('document_id', Uuid, primary_key=True), Column('tag_id', Uuid, primary_key=True))
        metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner, self.other, self.correspondent = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.tag_a, self.tag_b = self.tag('Versicherung'), self.tag('Auto')
        self.source = self.document('Quelle', tags=[self.tag_a, self.tag_b], correspondent=self.correspondent)
        self.service = RelatedDocumentService(self.db, self.owner)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def tag(self, name, owner=None):
        key = uuid.uuid4()
        self.db.execute(self.tags.insert().values(id=key, owner_id=owner or self.owner, name=name))
        return key

    def document(self, title, tags=(), correspondent=None, kind='Rechnung', owner=None, deleted=False, day=1):
        key = uuid.uuid4()
        self.db.execute(self.documents.insert().values(
            id=key, owner_id=owner or self.owner, original_filename=f'{title}.pdf', display_name=title,
            document_type=kind, correspondent_id=correspondent, is_deleted=deleted,
            document_date=date(2026, 10, day), created_at=datetime(2026, 10, day)))
        for tag in tags:
            self.db.execute(self.links.insert().values(document_id=key, tag_id=tag))
        return key

    def test_combined_correspondent_and_type_then_tags_then_correspondent(self):
        corr_only = self.document('Absender', kind='Vertrag', correspondent=self.correspondent)
        two_tags = self.document('Tags', kind='Vertrag', tags=[self.tag_a, self.tag_b])
        combined = self.document('Kombination', kind=' rechnung ', correspondent=self.correspondent)
        single_tag = self.document('Ein Tag', kind='Vertrag', tags=[self.tag_a])
        self.document('Nur Typ')
        result = self.service.list(self.source).items
        self.assertEqual([item.id for item in result], [combined, two_tags, corr_only, single_tag])
        self.assertTrue(result[0].same_type)
        self.assertTrue(result[0].same_correspondent)
        self.assertEqual(result[1].shared_tag_count, 2)
        self.assertEqual(result[1].shared_tags, ['Auto', 'Versicherung'])

    def test_excludes_self_trash_and_other_owners(self):
        own = self.document('Eigene', tags=[self.tag_a])
        self.document('Papierkorb', tags=[self.tag_a], deleted=True)
        self.document('Andere Person', tags=[self.tag_a], correspondent=self.correspondent, owner=self.other)
        self.assertEqual([item.id for item in self.service.list(self.source).items], [own])

    def test_foreign_missing_or_trashed_source_is_not_found(self):
        foreign = self.document('Fremd', owner=self.other)
        trashed = self.document('Geloescht', deleted=True)
        for document_id in [foreign, trashed, uuid.uuid4()]:
            with self.assertRaises(NotFoundError):
                self.service.list(document_id)

    def test_type_alone_and_blank_metadata_do_not_create_matches(self):
        empty = self.document('Keine Metadaten', kind=None)
        type_only = self.document('Nur Typ', kind='Rechnung')
        self.assertEqual(self.service.list(empty).items, [])
        self.assertEqual(self.service.list(type_only).items, [])

    def test_owner_scoping_also_applies_to_tag_names(self):
        foreign_tag = self.tag('Geheim', owner=self.other)
        source = self.document('Quelle 2', tags=[foreign_tag])
        self.document('Kandidat', tags=[foreign_tag])
        self.assertEqual(self.service.list(source).items, [])

    def test_limit_and_recent_date_tiebreak(self):
        documents = [self.document(f'Rechnung {i}', correspondent=self.correspondent, day=i) for i in range(1, 9)]
        result = self.service.list(self.source, limit=3).items
        self.assertEqual([item.id for item in result], list(reversed(documents))[:3])
        self.assertEqual(len(self.service.list(self.source).items), 5)

    def test_tag_explanations_are_capped_but_count_is_complete(self):
        extra = [self.tag(f'Tag {i}') for i in range(5)]
        source = self.document('Viele Tags', tags=extra)
        self.document('Treffer', tags=extra)
        item = self.service.list(source).items[0]
        self.assertEqual(item.shared_tag_count, 5)
        self.assertEqual(len(item.shared_tags), 3)


if __name__ == '__main__':
    unittest.main()

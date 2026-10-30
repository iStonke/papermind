import unittest
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, MetaData, Table, Text, Uuid, create_engine
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.services.related_documents import RelatedDocumentService
from app.schemas.related_preferences import RelatedPreferences


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

    def test_specific_overlap_beats_broad_metadata_and_weak_matches_are_omitted(self):
        corr_only = self.document('Absender', kind='Vertrag', correspondent=self.correspondent)
        two_tags = self.document('Tags', kind='Vertrag', tags=[self.tag_a, self.tag_b])
        combined = self.document('Kombination', kind=' rechnung ', correspondent=self.correspondent)
        single_tag = self.document('Ein Tag', kind='Vertrag', tags=[self.tag_a])
        self.document('Nur Typ')
        result = self.service.list(self.source).items
        self.assertEqual([item.id for item in result], [two_tags, combined])
        self.assertTrue(result[1].same_type)
        self.assertTrue(result[1].same_correspondent)
        self.assertEqual(result[0].shared_tag_count, 2)
        self.assertEqual(result[0].shared_tags, ['Auto', 'Versicherung'])

    def test_profiles_change_real_order_and_preview_does_not_write_documents(self):
        self.db.execute(self.documents.update().where(self.documents.c.id == self.source).values(display_name='Beitrag Sonnenversicherer Januar 2026'))
        series = self.document('Beitrag Sonnenversicherer Februar 2025', correspondent=self.correspondent)
        thematic = self.document('Anderes Thema', tags=[self.tag_a, self.tag_b], kind='Vertrag')
        process = self.service.list(self.source, preferences=RelatedPreferences(profile='process'))
        self.assertEqual(process.items[0].id, series)
        theme = self.service.list(self.source, preferences=RelatedPreferences(profile='thematic'))
        self.assertEqual(theme.items[0].id, thematic)
        self.assertEqual(self.service.list(self.source).items[0].id, series)

    def test_custom_weights_preserve_filters_and_do_not_create_type_only_matches(self):
        sender = self.document('Nur Absender', correspondent=self.correspondent, kind='Vertrag')
        self.document('Nur Typ')
        preferences = RelatedPreferences(profile='custom', weights={'correspondent': 'high', 'type': 'high', 'tags': 'low'})
        result = self.service.list(self.source, preferences=preferences)
        self.assertEqual([item.id for item in result.items], [sender])
        self.assertEqual(self.service.list(self.source, mode='tags', preferences=preferences).items, [])

    def test_excludes_self_trash_and_other_owners(self):
        own = self.document('Eigene', tags=[self.tag_a])
        self.document('Papierkorb', tags=[self.tag_a], deleted=True)
        self.document('Andere Person', tags=[self.tag_a], correspondent=self.correspondent, owner=self.other)
        self.assertEqual([item.id for item in self.service.list(self.source, mode="tags").items], [own])

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

    def test_pages_follow_relevance_then_proximity_to_source_date(self):
        documents = [self.document(f'Rechnung {i}', correspondent=self.correspondent, day=i) for i in range(1, 9)]
        result = self.service.list(self.source, limit=3).items
        self.assertEqual([item.id for item in result], documents[:3])
        second = self.service.list(self.source, limit=3, offset=3)
        self.assertEqual([item.id for item in second.items], documents[3:6])
        self.assertEqual(second.total, 8)
        self.assertTrue(second.has_more)
        final = self.service.list(self.source, limit=3, offset=6)
        self.assertEqual([item.id for item in final.items], documents[6:])
        self.assertFalse(final.has_more)
        self.assertEqual(len(self.service.list(self.source).items), 5)

    def test_tag_explanations_are_capped_but_count_is_complete(self):
        extra = [self.tag(f'Tag {i}') for i in range(5)]
        source = self.document('Viele Tags', tags=extra)
        self.document('Treffer', tags=extra)
        item = self.service.list(source).items[0]
        self.assertEqual(item.shared_tag_count, 5)
        self.assertEqual(len(item.shared_tags), 3)

    def test_rare_tags_outrank_a_common_label(self):
        generic, specific = self.tag('Rechnung'), self.tag('Kfz-Haftpflichtversicherung')
        source = self.document('Quelle', tags=[generic, specific])
        common = self.document('Allgemeine Rechnung', tags=[generic])
        precise = self.document('Versicherungspolice', tags=[specific])
        for index in range(30):
            self.document(f'Weitere Rechnung {index}', tags=[generic])
        result = self.service.list(source)
        self.assertEqual(result.items[0].id, precise)
        self.assertNotIn(common, [item.id for item in result.items])
        expanded = self.service.list(source, mode='tags', limit=20)
        self.assertEqual(expanded.total, 32)
        self.assertTrue(expanded.has_more)

    def test_overlap_accounts_for_many_unrelated_candidate_tags(self):
        precise = self.document('Passend', tags=[self.tag_a, self.tag_b])
        broad = self.document('Breit', tags=[self.tag_a, self.tag_b] + [self.tag(f'Extra {i}') for i in range(10)])
        result = self.service.list(self.source, mode='tags')
        self.assertEqual([item.id for item in result.items], [precise, broad])

    def test_title_series_ignore_months_years_and_suffixes(self):
        source = self.document('Beitragsrechnung Kfz-Versicherung Januar 2024.pdf')
        previous = self.document('Beitragsrechnung_Kfz_Versicherung_Oktober_2023.PDF')
        related = self.document('Nachtrag Kfz Versicherung')
        self.document('Beitragsrechnung Privathaftpflichtversicherung Oktober 2023')
        self.document('Rechnung Osteopathie 30.04.2024')
        result = self.service.list(source)
        self.assertEqual([item.id for item in result.items], [previous, related])
        self.assertTrue(result.items[0].same_series)
        self.assertTrue(result.items[1].similar_title)

    def test_meaningful_title_matches_work_without_tags_sender_or_type(self):
        source = self.document('Grundlagen Computergrafik 2024', kind=None)
        match = self.document('Grundlagen Computergrafik 2025', kind=None)
        self.document('Grundlagen Rechnungswesen 2025', kind=None)
        result = self.service.list(source)
        self.assertEqual([item.id for item in result.items], [match])
        self.assertTrue(result.items[0].similar_title)
        generic = self.document('Rechnung 2024', kind=None)
        self.document('Rechnung 2025', kind=None)
        self.assertEqual(self.service.list(generic).items, [])

    def test_a_generic_shared_tag_does_not_link_unrelated_invoices(self):
        generic = self.tag('Rechnung')
        source = self.document('Beitragsrechnung Kfz Versicherung Januar 2024', tags=[generic])
        unrelated = self.document('Rechnung Osteopathie April 2024', tags=[generic])
        self.assertEqual(self.service.list(source).items, [])
        self.assertEqual([item.id for item in self.service.list(source, mode='tags').items], [unrelated])

    def test_filters_expand_the_selection_without_mixing_sender_and_tags(self):
        sender = self.document('Absender', correspondent=self.correspondent, kind='Vertrag')
        tags = self.document('Tags', tags=[self.tag_a], kind='Vertrag')
        both = self.document('Beide', correspondent=self.correspondent, tags=[self.tag_b])
        by_sender = self.service.list(self.source, mode='correspondent')
        by_tags = self.service.list(self.source, mode='tags')
        self.assertEqual({item.id for item in by_sender.items}, {sender, both})
        self.assertEqual({item.id for item in by_tags.items}, {tags, both})
        unassigned = self.document('Ohne Zuordnung')
        for mode in ['correspondent', 'tags']:
            empty = self.service.list(unassigned, mode=mode)
            self.assertEqual(empty.total, 0)
            self.assertFalse(empty.has_more)

    def test_foreign_library_does_not_affect_rarity_or_title_results(self):
        own = self.document('Kfz Versicherung 2025', tags=[self.tag_a, self.tag_b])
        before = self.service.list(self.source)
        for index in range(15):
            self.document(f'Kfz Versicherung {index}', tags=[self.tag_a, self.tag_b], owner=self.other)
        after = self.service.list(self.source)
        self.assertEqual([item.id for item in before.items], [own])
        self.assertEqual([item.id for item in after.items], [own])
        self.assertEqual(before.total, after.total)


if __name__ == '__main__':
    unittest.main()

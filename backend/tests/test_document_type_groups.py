import unittest
import uuid
from unittest.mock import MagicMock

from sqlalchemy import Boolean, Column, MetaData, Table, Text, Uuid, create_engine, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.documents import DocumentSortField, DocumentSearchScope, SortOrder
from app.services.document_query_service import DocumentQueryService
from app.services.smart_folders import SmartFolderService


class DocumentTypeGroupsTest(unittest.TestCase):
    def test_counts_include_all_matching_documents_with_owner_scope_and_normalized_missing_types(self):
        owner = uuid.uuid4()
        engine = create_engine('sqlite://')
        table = Table('documents', MetaData(), Column('id', Uuid, primary_key=True),
                      Column('owner_id', Uuid), Column('document_type', Text),
                      Column('is_deleted', Boolean), Column('status', Text))
        table.create(engine)
        records = [dict(id=uuid.uuid4(), owner_id=owner, document_type=name, is_deleted=False, status='ready')
                   for name in ['Rechnung', 'rechnung', ' Rechnung '] * 40 + [None, '', '  ']]
        records += [dict(id=uuid.uuid4(), owner_id=uuid.uuid4(), document_type='Fremd', is_deleted=False, status='ready'),
                    dict(id=uuid.uuid4(), owner_id=owner, document_type='Gelöscht', is_deleted=True, status='ready'),
                    dict(id=uuid.uuid4(), owner_id=owner, document_type='Fehler', is_deleted=False, status='failed')]
        with engine.begin() as connection:
            connection.execute(table.insert(), records)
        with Session(engine) as session:
            query = DocumentQueryService(session, owner)
            source = query._scope(select(Document)).where(Document.is_deleted.is_(False), Document.status == 'ready')
            groups = query.document_type_groups(source)
            self.assertEqual({group.document_type: group.count for group in groups}, {None: 3, 'Rechnung': 120})
        engine.dispose()

    def test_untyped_filter_applies_before_group_count_and_pagination(self):
        db = MagicMock()
        db.execute.return_value.all.return_value = []
        db.execute.return_value.scalars.return_value.unique.return_value.all.return_value = []
        query = DocumentQueryService(db, uuid.uuid4())
        query.list_documents(q=None, tag=None, tag_ids=None, untagged=False, status=None,
                             date_from=None, date_to=None, recent_imports=False,
                             sort=DocumentSortField.correspondent_date, order=SortOrder.desc,
                             limit=50, offset=50, include_total=False,
                             without_document_type=True, include_document_type_groups=True)
        statements = [str(call.args[0]) for call in db.execute.call_args_list]
        self.assertEqual(len(statements), 2)
        self.assertTrue(all('coalesce(trim(documents.document_type)' in sql for sql in statements))
        self.assertTrue(all('documents.owner_id' in sql for sql in statements))
        self.assertNotIn('LIMIT', statements[0])
        self.assertNotIn('OFFSET', statements[0])
        self.assertIn('GROUP BY lower', statements[0])
        self.assertIn('documents.document_date DESC NULLS LAST', statements[1])

    def test_type_group_filter_preserves_folder_expression_and_search(self):
        service = SmartFolderService(MagicMock(), uuid.uuid4())
        service.get_smart_folder_or_404 = MagicMock(return_value=MagicMock(query_json={}))
        service.compiler.compile = MagicMock(return_value=Document.is_favorite.is_(True))
        service._list_documents = MagicMock()
        service.list_folder_documents(uuid.uuid4(), q='Strom', search_scope=DocumentSearchScope.title,
                                      document_type='Rechnung', include_document_type_groups=True)
        sql = str(service._list_documents.call_args.args[0])
        self.assertIn('documents.is_favorite', sql)
        self.assertIn('lower(trim(documents.document_type))', sql)
        self.assertIn('display_name', sql)
        self.assertTrue(service._list_documents.call_args.kwargs['include_document_type_groups'])
        service.list_folder_documents(uuid.uuid4(), without_document_type=True)
        self.assertIn('coalesce(trim(documents.document_type)', str(service._list_documents.call_args.args[0]))


if __name__ == '__main__':
    unittest.main()

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import event, text

from app.db.session import SessionLocal
from app.models.document import Document
from app.models.user import User
from app.schemas.documents import DocumentSortField, SortOrder
from app.services.document_query_service import DocumentQueryService
from app.services.document_snippet_cache import SnippetCache, snippet_cache


def query(db, owner):
    return DocumentQueryService(db, owner).list_documents(q='Rechnung', tag=None, tag_ids=None,
        untagged=False, status=None, date_from=None, date_to=None, recent_imports=False,
        sort=DocumentSortField.created_at, order=SortOrder.desc, limit=20, offset=0)


def test_repeated_search_reuses_headline_and_edits_invalidate_it():
    with SessionLocal() as db:
        owners = [User(username='snippet-' + uuid.uuid4().hex, password_hash='x', is_active=True) for _ in range(2)]
        db.add_all(owners); db.flush()
        doc = Document(owner_id=owners[0].id, original_filename='test.pdf', text_content='Eine Rechnung mit alter vertraulicher Beschreibung.')
        db.add(doc); db.commit(); owner_ids = [owner.id for owner in owners]; document_id = doc.id
    statements = []
    def observed(conn, cursor, statement, parameters, context, many):
        if 'ts_headline(' in statement: statements.append(statement)
    try:
        with SessionLocal() as db:
            event.listen(db.connection(), 'before_cursor_execute', observed)
            first = query(db, owner_ids[0]); second = query(db, owner_ids[0])
            assert len(statements) == 1
            assert first.items[0].snippet == second.items[0].snippet
            assert query(db, owner_ids[1]).items == []
            assert len(statements) == 1
        with SessionLocal() as db:
            db.get(Document, document_id).text_content = 'Eine Rechnung mit neuer geänderter Beschreibung.'
            db.commit()
        with SessionLocal() as db:
            event.listen(db.connection(), 'before_cursor_execute', observed)
            updated = query(db, owner_ids[0])
            assert len(statements) == 2
            assert updated.items[0].snippet != first.items[0].snippet
            assert 'neuer' in updated.items[0].snippet
    finally:
        with SessionLocal() as db:
            for owner in owner_ids: db.execute(text('DELETE FROM users WHERE id=:id'), {'id': owner})
            db.commit()


def test_cache_expires_and_bounds_memory_without_changing_large_headlines():
    cache = SnippetCache(max_entries=2, ttl_seconds=10)
    with patch('app.services.document_snippet_cache.time.monotonic', return_value=100):
        for key in range(3): cache.put(key, 'snippet')
        assert cache.get(0) == (False, None)
        assert cache.get(1) == (True, 'snippet')
        cache.put('large', 'x' * 8193)
        assert cache.get('large') == (False, None)
        cache.put('empty', None)
        assert cache.get('empty') == (True, None)
    with patch('app.services.document_snippet_cache.time.monotonic', return_value=111):
        assert cache.get('empty') == (False, None)

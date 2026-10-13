import assert from 'node:assert/strict';
import { test } from 'node:test';
import { documentTypeGroupKey, documentTypeRequestPath, prepareDocumentTypeGroups } from '../src/workspaces/documents/documentTypeView.js';

test('document type groups sort by name, put missing types last and have stable case-independent keys', () => {
  const groups = prepareDocumentTypeGroups([
    { document_type: null, count: 3 },
    { document_type: 'Vertrag', count: 120 },
    { document_type: 'Rechnung', count: 5 },
  ]);
  assert.deepEqual(groups.map(group => group.label), ['Rechnung', 'Vertrag', 'Ohne Dokumenttyp']);
  assert.equal(documentTypeGroupKey(' Rechnung '), documentTypeGroupKey('rechnung'));
  assert.equal(documentTypeGroupKey('  '), 'unassigned');
  assert.equal(groups.at(-1).unassigned, true);
  assert.equal(groups.reduce((total, group) => total + group.count, 0), 128);
  assert.equal(documentTypeGroupKey('Lohn / Gehalt & Steuer'), 'type:lohn%20%2F%20gehalt%20%26%20steuer');
});

test('summary requests preserve search and all filters without loading a whole collection', () => {
  const params = new URLSearchParams(documentTypeRequestPath('/api/documents?tag_ids=a&tag_ids=b&correspondent_id=c&q=Rechnung&search_scope=document_type&date_from=2026-01-01&status=ready&offset=100').split('?')[1]);
  assert.equal(params.get('include_document_type_groups'), 'true');
  assert.equal(params.get('include_total'), 'false');
  assert.equal(params.get('limit'), '1');
  assert.equal(params.get('offset'), '0');
  assert.equal(params.get('q'), 'Rechnung');
  assert.equal(params.get('search_scope'), 'document_type');
  assert.equal(params.get('correspondent_id'), 'c');
  assert.equal(params.get('date_from'), '2026-01-01');
  assert.equal(params.get('status'), 'ready');
  assert.deepEqual(params.getAll('tag_ids'), ['a', 'b']);
});

test('group pagination encodes type names and keeps folder, filters and document date order', () => {
  const path = documentTypeRequestPath('/api/smart-folders/folder-1/documents?q=Vertrag&search_scope=document_type', {
    group: { document_type: 'Vertrag & Vereinbarung' }, offset: 50,
  });
  assert.ok(path.startsWith('/api/smart-folders/folder-1/documents?'));
  const params = new URLSearchParams(path.split('?')[1]);
  assert.equal(params.get('document_type'), 'Vertrag & Vereinbarung');
  assert.equal(params.get('search_scope'), 'document_type');
  assert.equal(params.get('offset'), '50');
  assert.equal(params.get('limit'), '50');
  assert.equal(params.get('sort'), 'doc_date_desc');
  const untyped = new URLSearchParams(documentTypeRequestPath('/api/documents?tag_id=t&without_text=true', {
    group: { document_type: null },
  }).split('?')[1]);
  assert.equal(untyped.get('without_document_type'), 'true');
  assert.equal(untyped.get('tag_id'), 't');
  assert.equal(untyped.get('without_text'), 'true');
  assert.equal(untyped.has('document_type'), false);
});

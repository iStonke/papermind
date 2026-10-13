import assert from 'node:assert/strict';
import { test } from 'node:test';
import { correspondentInitials, correspondentRequestPath, prepareCorrespondentGroups, visibleDocumentTags } from '../src/workspaces/documents/correspondentView.js';

test('sorts groups alphabetically, keeps distinct IDs and places unassigned last', () => {
  const groups = prepareCorrespondentGroups([
    { correspondent_id: null, name: null, count: 8 },
    { correspondent_id: 'z', name: 'Zentrale', count: 12 },
    { correspondent_id: 'a-2', name: 'Andere Firma', short_name: 'ACME', count: 5 },
    { correspondent_id: 'a-1', name: 'ACME', count: 4 },
  ]);
  assert.deepEqual(groups.map(group => group.key), ['a-1', 'a-2', 'z', 'unassigned']);
  assert.equal(groups.at(-1).label, 'Ohne Korrespondent');
  assert.equal(groups.reduce((sum, group) => sum + group.count, 0), 29);
});

test('summary request retains all filters and does not request an entire document collection', () => {
  const path = correspondentRequestPath('/api/documents?tag_ids=t1&tag_ids=t2&q=Vertrag&search_scope=title&date_from=2025-01-01&status=ready&offset=100');
  const params = new URLSearchParams(path.split('?')[1]);
  assert.deepEqual(params.getAll('tag_ids'), ['t1', 't2']);
  assert.equal(params.get('q'), 'Vertrag');
  assert.equal(params.get('search_scope'), 'title');
  assert.equal(params.get('date_from'), '2025-01-01');
  assert.equal(params.get('status'), 'ready');
  assert.equal(params.get('limit'), '1');
  assert.equal(params.get('offset'), '0');
  assert.equal(params.get('include_correspondent_groups'), 'true');
});

test('group pagination keeps filters and uses document dates, including the unassigned group', () => {
  const path = correspondentRequestPath('/api/documents?without_text=true&tag_id=t1&sort=is_unread', { group: { correspondent_id: 'corr-1' }, offset: 50 });
  const params = new URLSearchParams(path.split('?')[1]);
  assert.equal(params.get('correspondent_id'), 'corr-1');
  assert.equal(params.get('without_text'), 'true');
  assert.equal(params.get('tag_id'), 't1');
  assert.equal(params.get('sort'), 'correspondent_date');
  assert.equal(params.get('offset'), '50');
  const unassigned = new URLSearchParams(correspondentRequestPath('/api/documents?date_to=2026-12-31', { group: { correspondent_id: null } }).split('?')[1]);
  assert.equal(unassigned.get('without_correspondent'), 'true');
  assert.equal(unassigned.has('correspondent_id'), false);
  assert.equal(unassigned.get('date_to'), '2026-12-31');
});

test('smart folder requests preserve the folder and its field search', () => {
  const path = correspondentRequestPath('/api/smart-folders/folder-1/documents?q=KMTV&search_scope=correspondent', { group: { correspondent_id: 'corr-1' } });
  assert.ok(path.startsWith('/api/smart-folders/folder-1/documents?'));
  const params = new URLSearchParams(path.split('?')[1]);
  assert.equal(params.get('q'), 'KMTV');
  assert.equal(params.get('search_scope'), 'correspondent');
  assert.equal(params.get('sort'), 'doc_date_desc');
});

test('initials support abbreviations and names', () => {
  assert.equal(correspondentInitials('KMTV'), 'KMTV');
  assert.equal(correspondentInitials('Techniker Krankenkasse'), 'TK');
  assert.equal(correspondentInitials('Amazon'), 'AM');
  assert.equal(correspondentInitials(''), '');
});

test('correspondent types have readable labels and symbols; missing types remain unobtrusive', () => {
  const groups = prepareCorrespondentGroups([
    { correspondent_id: 'org', name: 'A', kind: 'organization', count: 1 },
    { correspondent_id: 'person', name: 'B', kind: 'person', count: 1 },
    { correspondent_id: 'collection', name: 'C', kind: 'collection', count: 1 },
    { correspondent_id: 'untyped', name: 'D', kind: null, count: 1 },
    { correspondent_id: null, name: null, kind: null, count: 1 },
  ]);
  assert.deepEqual(groups.map(group => group.kindLabel), ['Organisation', 'Person', 'Sammlung', '', '']);
  assert.deepEqual(groups.map(group => group.kindIcon), ['mdi-domain', 'mdi-account-outline', 'mdi-shape-outline', '', '']);
});

test('the same tags stay visible when list and detail responses have different orders', () => {
  const tags = [
    { id: 't', name: 'Tanzschule' },
    { id: 'j', name: 'Jugend-Grundkurs' },
    { id: 'z', name: 'Zahlung' },
  ];
  const original = [...tags];
  assert.deepEqual(visibleDocumentTags({ tags }).map(tag => tag.name), ['Jugend-Grundkurs', 'Tanzschule']);
  assert.deepEqual(visibleDocumentTags({ tags: [...tags].reverse() }), visibleDocumentTags({ tags }));
  assert.deepEqual(tags, original);
  assert.deepEqual(visibleDocumentTags({}), []);
});

test('visible tags reflect actual edits and use a stable order for equivalent names', () => {
  const tags = [{ id: '2', name: 'Kurs' }, { id: '1', name: 'kurs' }];
  assert.deepEqual(visibleDocumentTags({ tags }).map(tag => tag.id), ['1', '2']);
  assert.deepEqual(visibleDocumentTags({ tags: tags.toReversed() }).map(tag => tag.id), ['1', '2']);
  assert.deepEqual(visibleDocumentTags({ tags: [{ id: 't', name: 'Geänderter Tag' }] }).map(tag => tag.name), ['Geänderter Tag']);
});

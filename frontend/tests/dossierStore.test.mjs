import test from 'node:test';
import assert from 'node:assert/strict';

import { createPinia, setActivePinia } from 'pinia';
import { useDossierStore } from '../src/stores/dossiers.js';

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    async json() { return payload; },
  };
}

test('setFavorite patches the flag and keeps list preview data', async () => {
  setActivePinia(createPinia());
  const store = useDossierStore();
  store.dossiers = [{
    id: 'd1',
    title: 'Auto',
    is_favorite: false,
    preview_document_ids: ['doc-1'],
  }];
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return jsonResponse({ id: 'd1', title: 'Auto', is_favorite: true });
  };

  try {
    await store.setFavorite('d1', true);
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls[0].url, '/api/dossiers/d1');
  assert.equal(calls[0].options.method, 'PATCH');
  assert.equal(calls[0].options.body, JSON.stringify({ is_favorite: true }));
  assert.equal(store.dossiers[0].is_favorite, true);
  assert.deepEqual(store.dossiers[0].preview_document_ids, ['doc-1']);
});

test('duplicate posts to the clone endpoint and reuses source preview fields', async () => {
  setActivePinia(createPinia());
  const store = useDossierStore();
  store.dossiers = [{
    id: 'd1',
    title: 'Auto',
    is_favorite: true,
    archived_at: '2026-08-01T00:00:00Z',
    item_count: 4,
    preview_document_ids: ['doc-1'],
    groups: [{ name: 'Werkstatt', count: 2 }],
    top_note: 'Termin HU',
  }];
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return jsonResponse({ id: 'd2', title: 'Auto (Kopie)', is_favorite: false, archived_at: null });
  };

  try {
    await store.duplicate('d1');
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls[0].url, '/api/dossiers/d1/duplicate');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(store.dossiers[0].id, 'd2');
  assert.equal(store.dossiers[0].is_favorite, false);
  assert.equal(store.dossiers[0].archived_at, null);
  assert.deepEqual(store.dossiers[0].preview_document_ids, ['doc-1']);
  assert.equal(store.dossiers[0].top_note, 'Termin HU');
});

test('batch remove and restore keep stable item ids and list counts', async () => {
  setActivePinia(createPinia());
  const store = useDossierStore();
  store.dossiers = [{ id: 'd1', item_count: 2, document_count: 1 }];
  store.items = [
    { id: 'doc-item', item_type: 'document', document_id: 'doc-1', sort_order: 1000 },
    { id: 'note-item', item_type: 'note', note_title: 'Prüfen', attached_to_item_id: 'doc-item', sort_order: 2000 },
  ];
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/batch-restore')) {
      return jsonResponse({ items: [
        { id: 'doc-item', dossier_id: 'd1', item_type: 'document', document_id: 'doc-1', sort_order: 1000 },
        { id: 'note-item', dossier_id: 'd1', item_type: 'note', note_title: 'Prüfen', attached_to_item_id: 'doc-item', sort_order: 2000 },
      ] }, 201);
    }
    return jsonResponse({ ok: true });
  };

  try {
    const snapshots = await store.removeItems('d1', ['doc-item', 'note-item']);
    assert.equal(store.items.length, 0);
    assert.equal(store.dossiers[0].item_count, 0);
    await store.restoreItems('d1', snapshots);
  } finally {
    globalThis.fetch = previousFetch;
  }

  assert.equal(calls[0].url, '/api/dossiers/d1/items/batch-delete');
  assert.equal(calls[1].url, '/api/dossiers/d1/items/batch-restore');
  assert.deepEqual(store.items.map((item) => item.id), ['doc-item', 'note-item']);
  assert.equal(store.dossiers[0].item_count, 2);
  assert.equal(store.dossiers[0].document_count, 1);
});

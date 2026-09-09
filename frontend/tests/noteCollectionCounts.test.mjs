import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { useNotesStore } from '../src/stores/notes.js';

function setup() {
  setActivePinia(createPinia());
  const store = useNotesStore();
  store.activeCollectionId = 'studium';
  store.collections = [
    { id: 'arbeit', note_count: 3 },
    { id: 'studium', note_count: 1 },
  ];
  store.notes = [{ id: 'first', collection_id: 'studium' }];
  return store;
}

for (const fromTemplate of [false, true]) {
  test(`collection count follows creation${fromTemplate ? ' from a template' : ''}, deletion and undo`, async (t) => {
    const store = setup();
    const note = { id: 'second', collection_id: 'studium', title: '', body_json: { type: 'doc', content: [] } };
    t.mock.method(globalThis, 'fetch', async (url, options) => {
      assert.equal(options.method, 'POST');
      if (String(url).endsWith('/api/notes')) {
        assert.equal(JSON.parse(options.body).collection_id, 'studium');
      }
      return new Response(JSON.stringify(note), { headers: { 'Content-Type': 'application/json' } });
    });
    if (fromTemplate) await store.createFromTemplate('template');
    else await store.create();
    assert.equal(store.collections[1].note_count, 2);
    assert.equal(store.notes.length, 2);
    assert.equal(store.notes[0].collection_id, 'studium');
    await store.remove('second');
    assert.equal(store.collections[1].note_count, 1);
    await store.restore('second');
    assert.equal(store.collections[1].note_count, 2);
    assert.equal(store.collections[0].note_count, 3);
  });
}

test('failed creation leaves the collection count unchanged', async (t) => {
  const store = setup();
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: 'Failed' }), {
    status: 500, headers: { 'Content-Type': 'application/json' },
  }));
  await assert.rejects(store.create());
  assert.equal(store.collections[1].note_count, 1);
  assert.equal(store.notes.length, 1);
});

test('creation in another collection does not leak into the loaded active list', async (t) => {
  const store = setup();
  store.loaded = true;
  const note = {
    id: 'work-note',
    collection_id: 'arbeit',
    notebook_id: null,
    title: 'Arbeit',
    body_json: { type: 'doc', content: [{ type: 'paragraph' }] },
  };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(String(url).endsWith('/api/notes'), true);
    assert.equal(JSON.parse(options.body).collection_id, 'arbeit');
    return new Response(JSON.stringify(note), { headers: { 'Content-Type': 'application/json' } });
  });

  await store.create({ collection_id: 'arbeit' });

  assert.deepEqual(store.notes.map((item) => item.id), ['first']);
  assert.equal(store.collections[0].note_count, 4);
  assert.equal(store.collections[1].note_count, 1);
});

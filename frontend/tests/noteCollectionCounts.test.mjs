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

test('global notes stay available while the collection list changes', async (t) => {
  const store = setup();
  const items = [
    { id: 'work', collection_id: 'arbeit', is_favorite: true },
    { id: 'study', collection_id: 'studium', is_favorite: false },
  ];
  t.mock.method(globalThis, 'fetch', async url => {
    assert.equal(new URL(String(url), 'http://example.test').searchParams.has('collection_id'), false);
    return new Response(JSON.stringify({ items }), { headers: { 'Content-Type': 'application/json' } });
  });
  await store.fetchNotes();
  assert.deepEqual(store.notes.map(note => note.id), ['study']);
  assert.deepEqual(store.allNotes.map(note => note.id), ['work', 'study']);
  store.activeCollectionId = 'arbeit';
  await store.fetchNotes();
  assert.deepEqual(store.notes.map(note => note.id), ['work']);
  assert.equal(store.allNotes.filter(note => note.is_favorite).length, 1);
});

test('global note cache follows creation, favorite changes, deletion and restore', async (t) => {
  const store = setup();
  store.loaded = true;
  const note = { id: 'global', collection_id: 'arbeit', title: 'Global', body_json: { type: 'doc', content: [] }, is_favorite: false };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (options.method === 'PATCH') note.is_favorite = JSON.parse(options.body).is_favorite;
    return new Response(JSON.stringify(note), { headers: { 'Content-Type': 'application/json' } });
  });
  await store.create({ collection_id: 'arbeit' });
  assert.equal(store.allNotes[0].id, 'global');
  await store.setFavorite('global', true);
  assert.equal(store.allNotes[0].is_favorite, true);
  await store.remove('global');
  assert.equal(store.allNotes.length, 0);
  await store.restore('global');
  assert.equal(store.allNotes[0].id, 'global');
});

test('integrated templates cannot be deleted and create independent editable notes', async (t) => {
  const store = setup();
  let requests = 0;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    requests++;
    const payload = JSON.parse(options.body);
    assert.equal(payload.is_template, undefined);
    assert.equal(payload.body_json.attrs.lectureMode, true);
    assert.equal(payload.body_json.content[0].type, 'templateBox');
    assert.equal(payload.body_json.content[0].attrs.title, 'Vorlesung');
    assert.equal(payload.body_json.content[0].attrs.color, 'rose');
    assert.deepEqual(payload.body_json.content[0].content.map(field => field.attrs), [
      { label: 'Titel', hint: 'Meetingbezeichnung' },
      { label: 'Datum', hint: 'tt.mm.jjjj' },
      { label: 'Thema', hint: 'Um welche Themen ging es?' },
      { label: 'Klausurrelevanz', hint: 'Was war besonders wichtig?' },
    ]);
    assert.equal(payload.body_json.content.length, 2);
    assert.equal(payload.body_json.content[1].type, 'lectureSlide');
    return new Response(JSON.stringify({ ...payload, id: 'created-lecture', title: '' }), { headers: { 'Content-Type': 'application/json' } });
  });
  await assert.rejects(store.deletePermanently('builtin:lecture-start'), /geschützt/);
  await assert.rejects(store.trash('builtin:lecture-start'), /geschützt/);
  assert.equal(store.blockTemplates.some(template => template.builtin), false);
  assert.equal(requests, 0);
  const note = await store.createFromTemplate('builtin:lecture-start');
  assert.equal(note.id, 'created-lecture');
  assert.equal(requests, 1);
  assert.equal(store.templates[0].builtin, true);
});

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  NOTE_DRAFT_READ_TIMEOUT_MS,
  createNoteDraftVersion,
  getNoteDraft,
  resetNoteDraftReadPause,
  withNoteDraftTimeout,
  latestKnownNoteRevision,
  noteBodiesEqual,
  noteDraftMatchesServer,
  normalizeNoteDraftForStorage,
} from '../src/utils/noteDraftStorage.js';

const workspaceEditorSource = await readFile(
  new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url),
  'utf8',
);


test('local note draft comparison includes title and structured body', () => {
  const body = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Entwurf' }] }] };
  const draft = { title: 'Notiz', bodyJson: body };

  assert.equal(noteDraftMatchesServer(draft, { title: 'Notiz', body_json: body }), true);
  assert.equal(noteDraftMatchesServer(draft, { title: 'Andere Notiz', body_json: body }), false);
  assert.equal(noteDraftMatchesServer(draft, { title: 'Notiz', title_is_generated: true, body_json: body }), false);
  assert.equal(noteDraftMatchesServer(draft, {
    title: 'Notiz',
    body_json: { type: 'doc', content: [{ type: 'paragraph' }] },
  }), false);
});


test('structured note bodies compare semantically instead of by object key order', () => {
  const local = {
    type: 'doc',
    attrs: { linkedDocument: null, layout: 'paper' },
    content: [{ type: 'paragraph', attrs: { align: null, indent: 0 } }],
  };
  const server = {
    content: [{ attrs: { indent: 0, align: null }, type: 'paragraph' }],
    attrs: { layout: 'paper', linkedDocument: null },
    type: 'doc',
  };

  assert.equal(noteBodiesEqual(local, server), true);
  assert.equal(noteDraftMatchesServer(
    { title: 'Notiz', bodyJson: local },
    { title: 'Notiz', body_json: server },
  ), true);
});


test('a stale snapshot cannot lower the latest confirmed server revision', () => {
  assert.equal(latestKnownNoteRevision(4, 7, 6), 7);
  assert.equal(latestKnownNoteRevision(undefined, 0), 1);
  assert.match(
    workspaceEditorSource,
    /serverRevision: latestKnownNoteRevision\(snapshot\.baseRevision, activeRevision\)/,
  );
  assert.match(
    workspaceEditorSource,
    /pendingSnapshot\.baseRevision = pipeline\.serverRevision;[\s\S]*?persistLocalSnapshot\(pendingSnapshot\)/,
  );
});


test('local draft versions are non-empty and unique', () => {
  const first = createNoteDraftVersion();
  const second = createNoteDraftVersion();

  assert.ok(first);
  assert.ok(second);
  assert.notEqual(first, second);
});


test('local draft storage strips transient, non-serializable fields', () => {
  const body = { type: 'doc', content: [{ type: 'paragraph' }] };
  const stored = normalizeNoteDraftForStorage({
    noteId: 42,
    title: 'Entwurf',
    bodyJson: body,
    baseRevision: 3,
    clientVersion: 'draft-1',
    savedAt: 1234,
    localWritePromise: Promise.resolve(),
  });

  assert.deepEqual(stored, {
    noteId: '42',
    title: 'Entwurf',
    titleIsGenerated: false,
    bodyJson: body,
    baseRevision: 3,
    clientVersion: 'draft-1',
    savedAt: 1234,
  });
});

test('draft storage access gives up instead of waiting forever', async () => {
  await assert.rejects(
    withNoteDraftTimeout(new Promise(() => {}), 20, 'zu langsam'),
    /zu langsam/,
  );
  assert.equal(await withNoteDraftTimeout(Promise.resolve('ok'), 20, 'zu langsam'), 'ok');
});

test('a hanging IndexedDB connection is dropped and reopened on the next read', async () => {
  const previous = globalThis.indexedDB;
  const draft = { noteId: 'n1', title: 'Entwurf', clientVersion: 'v1' };
  const workingDb = {
    transaction: () => ({
      objectStore: () => ({
        get: () => {
          const request = {};
          setTimeout(() => { request.result = draft; request.onsuccess?.(); });
          return request;
        },
      }),
    }),
  };
  let opens = 0;
  globalThis.indexedDB = {
    open: () => {
      opens++;
      const request = {};
      // Erster Versuch hängt (Browser antwortet nie), zweiter klappt.
      if (opens > 1) setTimeout(() => { request.result = workingDb; request.onsuccess?.(); });
      return request;
    },
  };
  try {
    const started = Date.now();
    await assert.rejects(getNoteDraft('n1'), /nicht rechtzeitig/);
    assert.ok(Date.now() - started < NOTE_DRAFT_READ_TIMEOUT_MS + 500);
    // Danach kein erneutes Warten bei jedem Notizwechsel …
    const paused = Date.now();
    await assert.rejects(getNoteDraft('n1'), /zurzeit nicht/);
    assert.ok(Date.now() - paused < 50);
    assert.equal(opens, 1);
    // … und nach der Pause wird die Verbindung neu aufgebaut.
    resetNoteDraftReadPause();
    assert.deepEqual(await getNoteDraft('n1'), draft);
    assert.equal(opens, 2);
  } finally {
    globalThis.indexedDB = previous;
  }
});

test('switching notes never stays stuck on the previous note', () => {
  assert.match(workspaceEditorSource, /if \(cachedNote\) \{\s*try \{\s*await applyLoadedNote\(cachedNote, noteId\);\s*\} catch \(error\)/);
  assert.match(workspaceEditorSource, /console\.warn\('Lokaler Entwurf nicht verfügbar, Serverstand wird angezeigt:', error\)/);
});

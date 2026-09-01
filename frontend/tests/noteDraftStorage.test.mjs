import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  createNoteDraftVersion,
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
    bodyJson: body,
    baseRevision: 3,
    clientVersion: 'draft-1',
    savedAt: 1234,
  });
});

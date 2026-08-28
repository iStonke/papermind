import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createNoteDraftVersion,
  noteDraftMatchesServer,
  normalizeNoteDraftForStorage,
} from '../src/utils/noteDraftStorage.js';


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

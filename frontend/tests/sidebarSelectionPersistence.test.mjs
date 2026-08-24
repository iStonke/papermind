import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  consumeSidebarStartAfterLogin,
  markSidebarStartAfterLogin,
  normalizeSidebarSelection,
  persistSidebarSelection,
  readSidebarSelection,
} from '../src/utils/sidebarSelection.js';

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

test('sidebar selections are validated and survive storage round-trips', () => {
  const storage = memoryStorage();
  assert.equal(persistSidebarSelection({ kind: 'view', value: 'notes' }, storage), true);
  assert.deepEqual(readSidebarSelection(storage), { kind: 'view', value: 'notes' });

  assert.deepEqual(
    normalizeSidebarSelection({ kind: 'saved-search', value: ' folder-12 ' }),
    { kind: 'saved-search', value: 'folder-12' },
  );
  assert.equal(normalizeSidebarSelection({ kind: 'view', value: 'unknown' }), null);
  assert.equal(normalizeSidebarSelection({ kind: 'route', value: 'login' }), null);
});

test('the post-login start-page marker is consumed exactly once', () => {
  const storage = memoryStorage();
  markSidebarStartAfterLogin(storage);
  assert.equal(consumeSidebarStartAfterLogin(storage), true);
  assert.equal(consumeSidebarStartAfterLogin(storage), false);
});

test('login and workspace wire the one-shot start-page exception into restoration', async () => {
  const [loginSource, workspaceSource] = await Promise.all([
    readFile(new URL('../src/views/LoginView.vue', import.meta.url), 'utf8'),
    readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8'),
  ]);

  assert.match(loginSource, /markSidebarStartAfterLogin\(\)/);
  assert.match(workspaceSource, /consumeSidebarStartAfterLogin\(\)/);
  assert.match(workspaceSource, /readSidebarSelection\(\)/);
  assert.match(workspaceSource, /persistSidebarSelection\(currentSidebarSelection\.value\)/);
  assert.match(workspaceSource, /configuredStartSidebarSelection\(\)/);
});

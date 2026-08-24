import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const listPanelSource = await readFile(
  new URL('../src/components/DocumentListPanel.vue', import.meta.url),
  'utf8',
);
const executeEmptyTrashStart = workspaceSource.indexOf('async function executeEmptyTrash()');
const executeEmptyTrashEnd = workspaceSource.indexOf('/** Favoriten-Status', executeEmptyTrashStart);
const executeEmptyTrashSource = workspaceSource.slice(executeEmptyTrashStart, executeEmptyTrashEnd);

test('emptying the trash stays silent after success but still reports failures', () => {
  assert.ok(executeEmptyTrashStart >= 0 && executeEmptyTrashEnd > executeEmptyTrashStart);
  assert.doesNotMatch(executeEmptyTrashSource, /notify\(\{/);
  assert.match(executeEmptyTrashSource, /notifyError\(error, 'Papierkorb konnte nicht geleert werden\.'\)/);
});

test('emptying the trash animates every rendered item only after deletion succeeds', () => {
  assert.match(
    executeEmptyTrashSource,
    /if \(!response\.ok\)[\s\S]*await documentListPanelRef\.value\?\.animateTrashEmpty\?\.\(\)/,
  );
  assert.match(listPanelSource, /async function animateTrashEmpty\(\)/);
  assert.match(
    listPanelSource,
    /\.document-row\[data-document-id\], \.pm-trash-note\[data-trash-note-id\]/,
  );
  assert.match(listPanelSource, /TRASH_EMPTY_MAX_STAGGER_MS = 120/);
  assert.match(listPanelSource, /var\(--pm-removal-delay, 0ms\)/);
  assert.match(listPanelSource, /prefers-reduced-motion: reduce/);
});

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
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

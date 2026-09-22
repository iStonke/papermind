import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const dialogSource = await readFile(
  new URL('../src/components/ShortcutsHelpDialog.vue', import.meta.url),
  'utf8',
);

test('sidebar help action is placed before settings and opens the shortcuts dialog', () => {
  const actionsStart = workspaceSource.indexOf('<div class="sidebar-foot__actions">');
  const actionsEnd = workspaceSource.indexOf('</div>', actionsStart);
  const actions = workspaceSource.slice(actionsStart, actionsEnd);

  assert.ok(actions.indexOf('mdi-help-circle-outline') < actions.indexOf('mdi-cog-outline'));
  assert.match(actions, /aria-label="Tastenkürzel"/);
  assert.match(actions, /@click="openShortcutsHelp"/);
  assert.match(workspaceSource, /<ShortcutsHelpDialog v-model="uiStore\.shortcutsOpen" \/>/);
  assert.match(workspaceSource, /function openShortcutsHelp\(\) \{\s*uiStore\.openShortcuts\(\);/);
});

test('shortcuts dialog keeps the former controls help content in an accessible PaperMind dialog', () => {
  assert.match(dialogSource, /<BaseDialog/);
  assert.match(dialogSource, /title="Tastenkürzel"/);
  assert.match(dialogSource, /header-subtitle="Alle Tastaturkürzel und Mausgesten in PaperMind\."/);
  assert.match(dialogSource, /title: 'Mausgesten'/);
  assert.match(dialogSource, /SHORTCUT_ACTIONS\.CANCEL/);
});

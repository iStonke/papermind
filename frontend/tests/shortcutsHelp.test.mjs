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

test('sidebar shortcuts action lives in the overflow menu and opens the shortcuts dialog', () => {
  const actionsStart = workspaceSource.indexOf('<div class="sidebar-foot__actions">');
  const actionsEnd = workspaceSource.indexOf('</div>', actionsStart);
  const actions = workspaceSource.slice(actionsStart, actionsEnd);
  const directActions = actions.slice(0, actions.indexOf('<v-menu'));

  assert.doesNotMatch(directActions, /mdi-keyboard-outline/);
  assert.match(workspaceSource, /<v-list-item title="Tastenkürzel" @click="openShortcutsFromSidebarMenu">/);
  assert.match(workspaceSource, /function openShortcutsFromSidebarMenu\(\)/);
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

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [sidebarSource, settingsSource] = await Promise.all([
  readFile(new URL('../src/components/AppSidebar.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/SettingsDialog.vue', import.meta.url), 'utf8'),
]);

test('folder sidebar entries honor the configured maximum', () => {
  assert.match(settingsSource, /settingsDraft\.ui\.sidebar_max_folders/);
  assert.match(settingsSource, /onSidebarMaxFoldersChange/);
  assert.match(sidebarSource, /const maxSidebarFolders = computed/);
  assert.match(sidebarSource, /sortedFolderItems\.value\.slice\(0, maxSidebarFolders\.value\)/);
  assert.match(sidebarSource, /v-for="savedSearch in visibleFolderItems"/);
});

test('the full folder list remains available from the section header', () => {
  assert.match(sidebarSource, /aria-label="Alle Ordner anzeigen"/);
  assert.match(sidebarSource, /<v-list-subheader>Alle Ordner<\/v-list-subheader>/);
  assert.match(sidebarSource, /v-for="savedSearch in sortedFolderItems"/);
  assert.match(sidebarSource, /emit\('open-saved-search', savedSearch\.id\)/);
});

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
  assert.match(sidebarSource, /class="sidebar-section-label sidebar-section-label--action"[\s\S]*?aria-label="Alle Ordner anzeigen"[\s\S]*?>[\s\S]*?Ordner[\s\S]*?<\/button>/);
  assert.match(sidebarSource, /<v-list-subheader>Alle Ordner<\/v-list-subheader>/);
  assert.match(sidebarSource, /v-for="savedSearch in sortedFolderItems"/);
  assert.match(sidebarSource, /emit\('open-saved-search', savedSearch\.id\)/);
});

test('folder and tag section headers use calm text navigation with a dedicated disclosure button', () => {
  assert.match(sidebarSource, /aria-label="Alle Tags anzeigen"[\s\S]*?@click="emit\('open-tags-view'\)"[\s\S]*?>[\s\S]*?Tags[\s\S]*?<\/button>/);
  assert.doesNotMatch(sidebarSource, /aria-label="Alle (?:Ordner|Tags) anzeigen"[\s\S]{0,180}?mdi-view-grid-outline/);
  assert.match(sidebarSource, /class="sidebar-section-toggle"[\s\S]*?@click\.stop="toggleSection\('ordner'\)"/);
  assert.match(sidebarSource, /class="sidebar-section-toggle"[\s\S]*?@click\.stop="toggleSection\('tags'\)"/);
});

test('create-folder action stays quiet until pointer or keyboard interaction', () => {
  assert.match(sidebarSource, /class="sidebar-section-icon-action sidebar-section-create-action"[\s\S]*?aria-label="Ordner erstellen"/);
  assert.match(sidebarSource, /\.sidebar-section-create-action\s*\{[\s\S]*?opacity:\s*0;[\s\S]*?transform:\s*translateX\(3px\)/);
  assert.match(sidebarSource, /\.sidebar-section-header:hover \.sidebar-section-create-action,[\s\S]*?\.sidebar-section-header:focus-within \.sidebar-section-create-action[\s\S]*?opacity:\s*1/);
  assert.match(sidebarSource, /@media \(hover: none\)[\s\S]*?\.sidebar-section-create-action[\s\S]*?opacity:\s*0\.72/);
});

test('folder, tag and document-type header icons appear only on interaction', () => {
  assert.match(sidebarSource, /\.sidebar-section-header-actions\s*\{[\s\S]*?opacity:\s*0;[\s\S]*?pointer-events:\s*none;/);
  assert.match(sidebarSource, /\.sidebar-section-header:hover \.sidebar-section-header-actions,[\s\S]*?\.sidebar-section-header:focus-within \.sidebar-section-header-actions[\s\S]*?opacity:\s*1;[\s\S]*?pointer-events:\s*auto;/);
  assert.match(sidebarSource, /@media \(hover: none\)[\s\S]*?\.sidebar-section-header-actions[\s\S]*?opacity:\s*1;[\s\S]*?pointer-events:\s*auto;/);
});

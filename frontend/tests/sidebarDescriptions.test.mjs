import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const settingsSource = await readFile(new URL('../src/components/SettingsDialog.vue', import.meta.url), 'utf8');
const settingsStyles = await readFile(new URL('../src/components/SettingsDialog.styles.css', import.meta.url), 'utf8');
const sidebarSection = settingsSource
  .split(`<section v-if="activeCategory === 'sidebar'"`)[1]
  ?.split(`<section v-if="activeCategory === 'documents'"`)[0] || '';

function plainText(value) {
  return String(value || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

test('sidebar setting sublines describe their areas instead of repeating visibility controls', () => {
  const descriptions = [...sidebarSection.matchAll(/class="pm-setting-description">([\s\S]*?)<\/div>/g)]
    .map((match) => plainText(match[1]));

  assert.equal(descriptions.length, 9);
  for (const description of descriptions) {
    assert.doesNotMatch(description, /\banzeigen\b|Eintrag in der Seitenleiste/i);
    assert.ok(description.length >= 35, `Description is too short: ${description}`);
  }

  assert.match(sidebarSection, /Fragen an deine Dokumente stellen und geprüfte Wissensaussagen verwalten\./);
  assert.match(sidebarSection, /Erfasst Dokumente ohne erkannten Text oder verwertbaren Suchindex\./);
});

test('sidebar settings mirror the navigation icons beside their entries', () => {
  for (const icon of [
    'mdi-view-dashboard-outline',
    'mdi-table-furniture',
    'mdi-brain',
    'mdi-tray-arrow-down',
    'mdi-tag-off-outline',
    'mdi-text-box-remove-outline',
  ]) {
    assert.match(sidebarSection, new RegExp(`<v-icon size="18">${icon}<\\/v-icon>`));
  }
});

test('sidebar setting groups use spaced separators between the main areas', () => {
  assert.match(settingsStyles, /\.settings-sidebar-main \+ \.settings-sidebar-library,[\s\S]*?\.settings-sidebar-library \+ \.settings-sidebar-other\s*{[^}]*margin-top: 20px;[^}]*padding-top: 20px;[^}]*border-top:/);
});

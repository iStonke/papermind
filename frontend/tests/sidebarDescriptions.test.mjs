import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const settingsSource = await readFile(new URL('../src/components/SettingsDialog.vue', import.meta.url), 'utf8');
const sidebarSection = settingsSource
  .split(`<section v-if="activeCategory === 'sidebar'"`)[1]
  ?.split(`<section v-if="activeCategory === 'documents'"`)[0] || '';

function plainText(value) {
  return String(value || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

test('sidebar setting sublines describe their areas instead of repeating visibility controls', () => {
  const descriptions = [...sidebarSection.matchAll(/class="pm-setting-description">([\s\S]*?)<\/div>/g)]
    .map((match) => plainText(match[1]));

  assert.equal(descriptions.length, 10);
  for (const description of descriptions) {
    assert.doesNotMatch(description, /\banzeigen\b|Eintrag in der Seitenleiste/i);
    assert.ok(description.length >= 35, `Description is too short: ${description}`);
  }

  assert.match(sidebarSection, /Fragen an deine Dokumente stellen und geprüfte Wissensaussagen verwalten\./);
  assert.match(sidebarSection, /Erfasst Dokumente ohne erkannten Text oder verwertbaren Suchindex\./);
});

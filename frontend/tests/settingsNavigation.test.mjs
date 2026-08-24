import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(
  new URL('../src/components/SettingsDialog.vue', import.meta.url),
  'utf8',
);
const navigationStart = source.indexOf('const settingsCategories = [');
const navigationEnd = source.indexOf('const settingsCategoryGroups = [', navigationStart);
const navigation = source.slice(navigationStart, navigationEnd);

test('controls is the final category in the surface settings group', () => {
  const surfaceCategories = [...navigation.matchAll(
    /value: '([^']+)'[^\n]+group: 'surface'/g,
  )].map((match) => match[1]);

  assert.deepEqual(surfaceCategories, ['appearance', 'sidebar', 'documents', 'controls']);
});

test('notes has a dedicated settings area in the documents group', () => {
  assert.match(
    navigation,
    /value: 'notes', label: 'Notizen', icon: 'mdi-note-outline', group: 'documents'/,
  );
  assert.match(source, /<section v-if="activeCategory === 'notes'"/);
  assert.match(source, /subtitle="Globale Vorgaben für Notizenliste und Editor\."/);
  assert.match(source, />Standardansicht</);
  assert.match(source, />Standardsortierung</);
  assert.match(source, />Schreibbreite</);
  assert.match(source, />Absatzabstand</);
  assert.match(source, />Schriftart</);
  assert.match(source, />Rechtschreibprüfung</);
  assert.match(source, /notesDefaultViewOptions/);
  assert.match(source, /notesSortOrderOptions/);
  assert.match(source, /notesWritingWidthOptions/);
  assert.match(source, /notesParagraphSpacingOptions/);
  assert.match(source, /notesFontFamilyOptions/);
  assert.match(source, /notes_spellcheck_enabled/);
  assert.doesNotMatch(source, /Notiz-Einstellungen werden vorbereitet/);
});

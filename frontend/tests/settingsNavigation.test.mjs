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
const groupNavigationEnd = source.indexOf('];', navigationEnd);
const groupNavigation = source.slice(navigationEnd, groupNavigationEnd);

test('surface settings do not contain the separate controls area', () => {
  const surfaceCategories = [...navigation.matchAll(
    /value: '([^']+)'[^\n]+group: 'surface'/g,
  )].map((match) => match[1]);

  assert.deepEqual(surfaceCategories, ['appearance', 'sidebar', 'documents']);
  assert.doesNotMatch(navigation, /value: 'controls'/);
  assert.doesNotMatch(navigation, /label: 'Bedienung'/);
});

test('notes has a dedicated top-level settings group', () => {
  assert.match(navigation, /value: 'notes_general', label: 'Allgemein'[^\n]+group: 'notes'/);
  assert.match(navigation, /value: 'notes_text', label: 'Textdarstellung'[^\n]+group: 'notes'/);
  assert.match(navigation, /value: 'notes_spacing', label: 'Abstände'[^\n]+group: 'notes'/);
  assert.doesNotMatch(navigation, /value: 'notes_writing'/);
  assert.match(source, /<section v-if="activeCategory\.startsWith\('notes_'\)"/);
  assert.match(source, /activeCategory === 'notes_general'/);
  assert.match(source, /activeCategory === 'notes_text'/);
  assert.match(source, /activeCategory === 'notes_spacing'/);
  assert.match(source, /\['notes', 'notes_writing'\]\.includes\(categoryValue\)/);
  assert.match(source, /const normalized = normalizeSettingsCategory\(categoryValue\)/);
  assert.match(source, />Standardansicht</);
  assert.match(source, />Standardsortierung</);
  assert.match(source, />Schreibbreite</);
  assert.match(source, />Absatzabstand</);
  assert.match(source, />Schriftart</);
  assert.match(source, />Rechtschreibprüfung</);
  assert.match(source, />Textgröße</);
  assert.match(source, />Zeilenabstand</);
  assert.match(source, />Abstand vor Überschriften</);
  assert.match(source, />Abstand bei Inhaltsblöcken</);
  assert.match(source, /notes-settings-preview/);
  assert.match(source, /notesDefaultViewOptions/);
  assert.match(source, /notesSortOrderOptions/);
  assert.match(source, /notesWritingWidthOptions/);
  assert.match(source, /notesParagraphSpacingOptions/);
  assert.match(source, /notesFontFamilyOptions/);
  assert.match(source, /value: 'inter', label: 'Inter'/);
  assert.match(source, /value: 'source-sans', label: 'Source Sans 3'/);
  assert.match(source, /value: 'atkinson', label: 'Atkinson Hyperlegible'/);
  assert.match(source, /value: 'source-serif', label: 'Source Serif 4'/);
  assert.match(source, /notes_spellcheck_enabled/);
  assert.doesNotMatch(source, /Notiz-Einstellungen werden vorbereitet/);

  const textSettings = source.slice(
    source.indexOf(`<template v-if="activeCategory === 'notes_text'">`),
    source.indexOf(`<template v-if="activeCategory === 'notes_spacing'">`),
  );
  const spacingSettings = source.slice(
    source.indexOf(`<template v-if="activeCategory === 'notes_spacing'">`),
    source.indexOf(`<template v-if="activeCategory === 'notes_replacements'">`),
  );
  assert.doesNotMatch(textSettings, />Zeilenabstand</);
  assert.ok(spacingSettings.indexOf('>Zeilenabstand<') < spacingSettings.indexOf('>Absatzabstand<'));
});

test('notes and documents are separate top-level settings groups', () => {
  const groups = [...groupNavigation.matchAll(
    /key: '([^']+)', label: '[^']+'/g,
  )].map((match) => match[1]);

  assert.deepEqual(groups, ['surface', 'notes', 'documents', 'import', 'ai', 'system']);
});

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(
  new URL('../src/views/LernraumWorkspace.vue', import.meta.url),
  'utf8',
);

test('Lernraum follows one hierarchy from overview to course and sheet', () => {
  // Brotkrumen Startseite → Kurs → Lernblatt; jede Ebene führt eine Stufe zurück.
  assert.match(source, /<nav v-if="store\.courses\.length" class="lr-crumbs" aria-label="Pfad">/);
  assert.match(source, /<button v-else type="button" class="lr-crumb" @click="c\.go">/);
  assert.match(source, /const crumbs = computed\(\(\) => \{[\s\S]*?label: 'Startseite', go: goHome[\s\S]*?go: closeSheet[\s\S]*?openSheet\.value\.title, current: true/);
  assert.match(source, /function closeSheet\(\) \{\s*if \(!store\.activeCourseId\) return goHome\(\);\s*openCourse\(store\.activeCourseId\);/);
  assert.doesNotMatch(source, /class="lr-breadcrumb"/);
  assert.match(source, /function openCourse\(id\)[\s\S]*?query: \{ course:/);
  assert.match(source, /function openSheetView\(id\)[\s\S]*?sheet: String\(id\)/);
  assert.doesNotMatch(source, /class="lr-modetabs"/);
  assert.doesNotMatch(source, /@click="toggleCourse/);
});

test('learning is a focused route state with a defined return path', () => {
  assert.match(source, /v-if="learning" class="lr-focus lr-learning-focus"/);
  assert.match(source, /learn: '1', scope/);
  assert.match(source, /router\.back\(\)/);
  assert.match(source, /Durchlauf abgeschlossen/);
});

test('home reports aggregate progress and keeps review tasks compact', () => {
  assert.match(source, /const overallProficiency = computed/);
  assert.match(source, /const headerProficiency = computed/);
  assert.match(source, /Gesamter Lernfortschritt/);
  assert.match(source, /\.lr-task-list \{ display: grid; grid-template-columns: repeat\(auto-fill, minmax\(235px, 1fr\)\)/);
  assert.match(source, /class="lr-task-preview">\{\{ task\.marker\.snippet/);
  assert.match(source, /\.lr-task-preview \{[^}]*-webkit-line-clamp: 2/);
  assert.doesNotMatch(source, />Kurs anlegen<\/button>/);
  assert.doesNotMatch(source, /<div v-if="overallProficiency\.total" class="lr-progress-report">/);
});

test('course progress lives in the course header instead of a separate content card', () => {
  assert.match(source, /class="lr-header-progress lr-header-progress--actions"/);
  assert.match(source, /class="lr-progress-band"/);
  assert.match(source, /class="lr-progress-band-segment"\s*:style="\{ width: seg\.pct \+ '%', background: seg\.color \}"/);
  assert.match(source, /class="lr-header-progress-label"><strong>\{\{ pct\(headerProficiency, 'strong'\) \}\} %<\/strong> sicher/);
  assert.doesNotMatch(source, /class="lr-header-progress-score"/);
  assert.match(source, /Lernfortschritt des Kurses/);
  assert.doesNotMatch(source, /<section class="lr-course-overview">/);
});

test('learning starts per sheet instead of from a course-wide header action', () => {
  assert.match(source, /class="lr-sheet-tile-actions"/);
  assert.match(source, /@click="startSheetLearn\(sheet\)"/);
  assert.match(source, /async function startSheetLearn\(sheet\)/);
  assert.doesNotMatch(source, /startCourseLearnAll/);
});

test('clicking the course title edits it inline', () => {
  assert.match(source, /class="lr-title-edit"/);
  assert.match(source, /class="lr-title-input"/);
  assert.match(source, /@click="editCourseTitle"/);
  assert.match(source, /@keydown\.enter\.prevent="saveCourseTitle"/);
  assert.match(source, /store\.renameCourse\(store\.activeCourse\.id/);
  assert.doesNotMatch(source, /course-rename/);
});

test('learning sheets can be renamed inline and deleted from their tiles', () => {
  assert.match(source, /class="lr-sheet-tile-tools"/);
  assert.match(source, /@click="onRenameSheet\(sheet\)"/);
  assert.match(source, /@keydown\.enter\.prevent="saveSheetTitle"/);
  assert.match(source, /store\.patchSheet\(sheetId, \{ title \}\)/);
  assert.match(source, /@click="onDeleteSheet\(sheet\)"/);
  assert.match(source, /store\.removeSheet\(sheet\.id\)/);
  assert.doesNotMatch(source, /sheet-rename/);
});

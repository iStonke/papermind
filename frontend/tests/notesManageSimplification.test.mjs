import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const gridSource = await readFile(
  new URL('../src/components/notes/NotesManageGrid.vue', import.meta.url),
  'utf8',
);
const tagBarSource = await readFile(
  new URL('../src/components/notes/NoteTagBar.vue', import.meta.url),
  'utf8',
);
const inlineTagEditorSource = await readFile(
  new URL('../src/components/TagInlineEditor.vue', import.meta.url),
  'utf8',
);
const workspaceSource = await readFile(
  new URL('../src/views/NotesWorkspace.vue', import.meta.url),
  'utf8',
);
const documentsWorkspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const themeSource = await readFile(
  new URL('../src/theme/theme.css', import.meta.url),
  'utf8',
);
const headerStart = workspaceSource.indexOf('<header class="notes-ws__header">');
const headerEnd = workspaceSource.indexOf('</header>', headerStart);
const header = workspaceSource.slice(headerStart, headerEnd);

test('notes management switches between notes and templates in the centered header', () => {
  assert.ok(headerStart >= 0 && headerEnd > headerStart, 'workspace header should be present');
  assert.match(header, /v-if="isManageMode"/);
  assert.match(header, /class="notes-ws__manage-switch"/);
  assert.match(header, /role="tablist"/);
  assert.match(header, /manageFacet === 'notes'[\s\S]*?>Notizen</);
  assert.match(header, /manageFacet === 'templates'[\s\S]*?>Vorlagen</);
  assert.doesNotMatch(header, /notes-ws__manage-switch-count/);
  assert.doesNotMatch(workspaceSource, /\.notes-ws__manage-switch-count\s*\{/);
  assert.match(workspaceSource, /\.notes-ws__manage-switch\s*\{[\s\S]*?position:\s*absolute[\s\S]*?left:\s*50%/);
  assert.match(workspaceSource, /:facet="manageFacet"/);
});

test('notes management leaves deleted notes to the shared trash view', () => {
  assert.doesNotMatch(gridSource, /listNotes\(\{ inTrash: true \}\)/);
  assert.doesNotMatch(gridSource, /emptyNotesTrash|loadTrash|trashItems/);
  assert.match(gridSource, /title="In Papierkorb"/);
  assert.match(gridSource, /await notesStore\.remove\(note\.id\)/);
});

test('unlinked notes are not presented as a separate state', () => {
  assert.doesNotMatch(gridSource, /orphanNotes|badge--orphan|Ohne Verknüpfung|Verwaist/);
});

test('the card grid starts without its own navigation bar', () => {
  assert.doesNotMatch(gridSource, /nmg__facets|nmg__facet|facetDefs/);
  assert.match(gridSource, /facet: \{ type: String, default: 'notes' \}/);
});

test('used note tags filter the grid from a dedicated right sidebar', () => {
  assert.match(gridSource, /<aside[\s\S]*?v-if="facet === 'notes'"[\s\S]*?class="nmg__tag-sidebar"/);
  assert.match(gridSource, /v-for="tag in tagCloudItems"/);
  assert.match(gridSource, /@click="toggleTagFilter\(tag\.id\)"/);
  assert.match(gridSource, /items = items\.filter\(\(n\) => \(n\.tags \|\| \[\]\)\.some\(\(t\) => t\.id === activeTagId\.value\)\)/);
  assert.match(gridSource, /for \(const tag of note\.tags \|\| \[\]\)[\s\S]*?entry\.count \+= 1/);
  assert.match(gridSource, /const tagCloudItems = computed\(\(\) => usedTags\.value\)/);
  assert.match(gridSource, /\.nmg__tag-sidebar\s*\{[\s\S]*?width:\s*clamp\(270px, 27vw, 320px\)[\s\S]*?border-left:\s*1px solid var\(--pm-divider/);
  assert.doesNotMatch(gridSource, /nmg__tagfilter/);
});

test('tag sidebar mirrors the notes outline and search panel design', () => {
  assert.match(gridSource, /\.nmg__tag-sidebar\s*\{[\s\S]*?background:\s*color-mix\(in srgb, var\(--pm-app-surface, #fff\) 96%, var\(--pm-accent, #006b75\)\)/);
  assert.match(gridSource, /\.nmg__tag-sidebar-head\s*\{[\s\S]*?min-height:\s*49px[\s\S]*?padding:\s*7px 8px 7px 12px/);
  assert.doesNotMatch(gridSource, /\.nmg__tag-sidebar-head\s*\{[^}]*border-bottom:/);
  assert.match(gridSource, /<h2 class="nmg__tag-sidebar-title">Tags<\/h2>/);
  assert.match(gridSource, /\.nmg__tag-sidebar-title\s*\{[\s\S]*?margin:\s*0[\s\S]*?font-size:\s*0\.82rem[\s\S]*?text-align:\s*left/);
  assert.doesNotMatch(gridSource, /nmg__tag-sidebar-title-label/);
  assert.match(gridSource, /\.nmg__tag-cloud\s*\{[\s\S]*?flex:\s*1 1 auto[\s\S]*?padding:\s*4px 16px 18px/);
  assert.doesNotMatch(gridSource, /Nach Tag filtern|nmg__tag-cloud-label|nmg__tag-cloud-all/);
  assert.match(gridSource, /class="nmg__tag-cloud-chip"[\s\S]*?>[\s\S]*?Alle Notizen/);
  assert.match(gridSource, /\.nmg__tag-cloud-items\s*\{[\s\S]*?flex-wrap:\s*wrap[\s\S]*?gap:\s*7px/);
  assert.match(gridSource, /\.nmg__tag-cloud-chip\s*\{[\s\S]*?height:\s*26px[\s\S]*?max-width:\s*min\(220px, 100%\)[\s\S]*?border-radius:\s*15px[\s\S]*?background:\s*var\(--pm-detail-chip-bg\)[\s\S]*?box-shadow:\s*none[\s\S]*?font-size:\s*12\.5px/);
  assert.match(gridSource, /\.nmg__tag-cloud-chip\.is-active\s*\{[\s\S]*?border-color:\s*var\(--pm-accent[\s\S]*?background:\s*var\(--pm-accent[\s\S]*?color:\s*var\(--pm-on-accent/);
  assert.match(gridSource, /\.nmg__tag-cloud-chip\.is-active \.nmg__tag-cloud-count\s*\{[\s\S]*?color:\s*var\(--pm-on-accent/);
  assert.doesNotMatch(gridSource, /nmg__tag-cloud-symbol/);
  assert.match(gridSource, /\.nmg__tag-cloud-empty\s*\{[\s\S]*?justify-content:\s*center[\s\S]*?gap:\s*2px/);
  assert.doesNotMatch(gridSource, /box-shadow:\s*-14px 0 34px/);
});

test('the tag sidebar remains visible before the first note tag is assigned', () => {
  assert.doesNotMatch(gridSource, /v-if="facet === 'notes' && usedTags\.length"/);
  assert.match(gridSource, /v-if="!tagCloudItems\.length" class="nmg__tag-cloud-empty"/);
  assert.match(gridSource, /Noch keine Tags/);
});

test('management cards separate their compact tag area from the text snippet', () => {
  assert.match(gridSource, /<NoteTagBar[\s\S]*?compact/);
  assert.doesNotMatch(gridSource, /:max-visible=/);
  assert.match(gridSource, /\.nmg__card\s*\{[\s\S]*?height:\s*auto;[\s\S]*?flex-direction:\s*column;/);
  assert.match(gridSource, /\.nmg__snippet\s*\{[\s\S]*?-webkit-line-clamp:\s*3;/);
  assert.match(gridSource, /\.nmg__card-tags\s*\{[\s\S]*?margin:\s*3px -16px 0;[\s\S]*?padding:\s*9px 16px 1px;[\s\S]*?border-top:/);
  assert.match(gridSource, /\.nmg__card-foot\s*\{[\s\S]*?margin-top:\s*auto;/);
  assert.match(gridSource, /\.nmg__card-tags\s*\{[\s\S]*?overflow:\s*visible;/);
});

test('note cards and the document detail drawer share the same inline tag editor', () => {
  assert.match(tagBarSource, /<TagInlineEditor[\s\S]*?v-if="compact"/);
  assert.match(tagBarSource, /const compactTagItems = computed[\s\S]*?toLocaleLowerCase\('de-DE'\)\.includes\(query\)/);
  assert.match(documentsWorkspaceSource, /<TagInlineEditor[\s\S]*?ref="metadataTagsCombobox"/);
  assert.match(inlineTagEditorSource, /<v-chip[\s\S]*?closable[\s\S]*?class="pm-tags-input__chip"/);
  assert.match(inlineTagEditorSource, /<v-combobox[\s\S]*?multiple[\s\S]*?hide-selected[\s\S]*?no-filter/);
  assert.match(inlineTagEditorSource, /class="pm-tags-input__add"[\s\S]*?mdi-plus[\s\S]*?>Tag</);
  assert.match(inlineTagEditorSource, /\.pm-tags-input__chips\s*\{[\s\S]*?display:\s*contents;/);
  assert.match(inlineTagEditorSource, /\.pm-tags-input__field\.v-input--focused[\s\S]*?width:\s*104px;/);
  assert.doesNotMatch(inlineTagEditorSource, /\.pm-tags-input__chip\.v-chip:hover/);
  assert.doesNotMatch(inlineTagEditorSource, /transform:\s*translateY\(-1px\)/);
  assert.doesNotMatch(documentsWorkspaceSource, /\.pm-tags-input__chip\.v-chip:hover/);
});

test('each card owns its actions and the management grid has no multi-selection', () => {
  assert.match(gridSource, /v-for="note in group\.notes"[\s\S]*?<v-menu location="bottom end"/);
  assert.match(gridSource, /icon="mdi-dots-vertical"/);
  assert.match(gridSource, /title="Umbenennen"/);
  assert.match(gridSource, /title="Als Vorlage speichern"/);
  assert.match(gridSource, /title="Neue Notiz erstellen"/);
  assert.match(gridSource, /title="Vorlage löschen…"/);
  assert.doesNotMatch(gridSource, /nmg__bulkbar|selectedIds|selectAllVisible|type="checkbox"|is-selected/);
});

test('empty notes and templates use the centered animated document placeholder', () => {
  assert.doesNotMatch(gridSource, /<Transition[^>]*nmg-content/);
  assert.doesNotMatch(gridSource, /\.nmg-content-(?:enter|leave)/);
  assert.match(gridSource, /:key="`empty-\$\{facet\}`"[\s\S]*?<PmEmptyState[\s\S]*?size="sm"/);
  assert.doesNotMatch(gridSource, /<PmEmptyState[\s\S]*?:animated="false"[\s\S]*?\/>/);
  assert.match(gridSource, /\.nmg__empty\s*\{[\s\S]*?width:\s*100%;[\s\S]*?height:\s*100%;[\s\S]*?align-items:\s*center;[\s\S]*?justify-content:\s*center;/);
});

test('compact and management note cards share the document-list surface treatment', () => {
  for (const token of [
    '--pm-document-row-bg',
    '--pm-document-row-border',
    '--pm-document-row-shadow',
    '--pm-document-row-hover-border',
  ]) {
    assert.match(themeSource, new RegExp(token));
    assert.match(documentsWorkspaceSource, new RegExp(`var\\(${token}`));
    assert.match(workspaceSource, new RegExp(`var\\(${token}`));
    assert.match(gridSource, new RegExp(`var\\(${token}`));
  }
});

test('the management grid keeps its local position and content height during facet transitions', () => {
  assert.match(
    gridSource,
    /\.nmg__scroll\s*\{[\s\S]*?position:\s*relative;/,
  );
  assert.match(
    gridSource,
    /\.nmg__grid\s*\{[\s\S]*?display:\s*grid;[\s\S]*?align-content:\s*start;/,
  );
  assert.doesNotMatch(gridSource, /nmg-content-(?:enter|leave)/);
});

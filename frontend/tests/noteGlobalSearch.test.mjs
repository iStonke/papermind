import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const workspaceSource = fs.readFileSync(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const notesSource = fs.readFileSync(
  new URL('../src/views/NotesWorkspace.vue', import.meta.url),
  'utf8',
);
const searchSource = fs.readFileSync(
  new URL('../src/composables/useSearch.js', import.meta.url),
  'utf8',
);
const notesApiSource = fs.readFileSync(
  new URL('../src/api/notes.js', import.meta.url),
  'utf8',
);
const notesStoreSource = fs.readFileSync(
  new URL('../src/stores/notes.js', import.meta.url),
  'utf8',
);

test('global search and note-list search keep separate state', () => {
  assert.match(workspaceSource, /:model-value="globalSearchText"/);
  assert.match(workspaceSource, /<NotesWorkspace[\s\S]*?v-model:search-query="noteListSearchText"/);
  assert.match(workspaceSource, /v-model:search-scope="noteListSearchScope"/);
  assert.match(notesSource, /v-model="listSearchQuery"/);
  assert.match(notesSource, /listSearchScopeOptions/);
});

test('note searches use the backend full text endpoint without replacing the canonical list', () => {
  assert.match(notesApiSource, /params\.set\('q', String\(q\)\.trim\(\)\)/);
  assert.match(notesApiSource, /params\.set\('search_scope', searchScope\)/);
  assert.match(notesStoreSource, /async function searchNotes\(query,[\s\S]*?api\.listNotes\(\{ q: query, searchScope: scope, collectionId \}\)/);
  assert.doesNotMatch(
    notesStoreSource.match(/async function searchNotes[\s\S]*?\n  \}/)?.[0] || '',
    /notes\.value\s*=/,
  );
  assert.match(notesSource, /notesStore\.searchNotes\(query, \{ scope, collectionId: activeCollectionId\.value \}\)/);
  assert.match(notesSource, /NOTE_SEARCH_DEBOUNCE_MS\s*=\s*220/);
});

test('note search has stable loading, empty, count, and highlight states', () => {
  assert.match(notesSource, /resolvedSearchKey\.value === activeSearchKey\.value/);
  assert.match(notesSource, /Keine passenden Notizen/);
  assert.match(notesSource, /leere die Notizensuche/);
  assert.match(notesSource, /isSearchingNotes[\s\S]*?'Suche …'/);
  assert.match(notesSource, /class="notes-ws__search-part"[\s\S]*?'is-match': part\.match/);
  assert.match(notesSource, /color-mix\(in srgb, var\(--pm-accent\) 22%, transparent\)/);
});

test('typing in note search does not reload the hidden document list', () => {
  assert.match(
    searchSource,
    /activeView\.value === 'dashboard'[\s\S]*?activeView\.value === 'notes'[\s\S]*?return;/,
  );
  assert.match(
    searchSource,
    /!\['chat', 'dashboard', 'notes', 'search'\]\.includes\(activeView\.value\)[\s\S]*?fetchDocuments/,
  );
});

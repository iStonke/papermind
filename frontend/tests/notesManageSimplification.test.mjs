import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const gridSource = await readFile(
  new URL('../src/components/notes/NotesManageGrid.vue', import.meta.url),
  'utf8',
);
const templatesFolderSource = await readFile(
  new URL('../src/components/notes/Vorlagenmappe.vue', import.meta.url),
  'utf8',
);
const templateCardSource = await readFile(
  new URL('../src/components/notes/VorlagenCard.vue', import.meta.url),
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
const headerStart = workspaceSource.indexOf('<header class="notes-ws__header">', workspaceSource.indexOf('class="notes-ws__manage-panel"'));
const headerEnd = workspaceSource.indexOf('</header>', headerStart);
const header = workspaceSource.slice(headerStart, headerEnd);

test('notes management switches between notes and templates from the heading menu', () => {
  assert.ok(headerStart >= 0 && headerEnd > headerStart, 'workspace header should be present');
  assert.match(workspaceSource, /v-if="isManageMode"[\s\S]*?class="notes-ws__manage-panel"/);
  assert.match(header, /class="notes-ws__manage-view-trigger"/);
  assert.match(header, /aria-label="Ansicht wechseln"/);
  assert.match(header, /class="notes-ws__manage-view-trigger"[\s\S]*?<span>\{\{ manageFacet === 'templates' \? 'Vorlagen' : 'Notizen' \}\}<\/span>[\s\S]*?notes-ws__manage-view-chevron/);
  assert.match(header, /class="notes-ws__manage-view-menu"[\s\S]*?role="menu"/);
  assert.match(header, /role="menuitemradio"[\s\S]*?manageFacet = 'notes'/);
  assert.match(header, /role="menuitemradio"[\s\S]*?manageFacet = 'templates'/);
  assert.doesNotMatch(header, /notes-ws__manage-switch-count/);
  assert.doesNotMatch(workspaceSource, /\.notes-ws__manage-switch-count\s*\{/);
  assert.doesNotMatch(header, /class="notes-ws__manage-switch"/);
  assert.match(header, /mdi-file-document-multiple-outline/);
  assert.match(header, /mdi-note-outline/);
  assert.match(workspaceSource, /:facet="manageFacet"/);
});

test('notes management exposes a global notes and notebooks search in its header', () => {
  assert.match(header, /class="notes-ws__manage-search"/);
  assert.match(header, /type="search"[\s\S]*?aria-label="Notizen und Notizbücher durchsuchen"/);
  assert.doesNotMatch(header, /notes-ws__manage-search-results|role="dialog"/);
  assert.match(header, /@keydown="handleManageSearchKeydown"/);
  assert.match(workspaceSource, /:global-search-query="normalizedManageSearchQuery"/);
  assert.match(workspaceSource, /:global-search-notes="manageSearchNotes"/);
  assert.match(workspaceSource, /:global-search-notebooks="matchingManageNotebooks"/);
  assert.match(gridSource, /v-if="isGlobalSearching"[\s\S]*?class="nmg-search-results"/);
  assert.match(gridSource, /<Transition name="nmg-content" mode="out-in">/);
  assert.match(gridSource, /\.nmg-content-enter-active,[\s\S]*?transition:\s*opacity 150ms ease/);
  assert.match(gridSource, /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.nmg-content-enter-active/);
  assert.match(gridSource, /globalSearchNotebooks[\s\S]*?>Notizbücher/);
  assert.match(gridSource, /filteredGlobalSearchNotes[\s\S]*?>Notizen/);
  assert.match(gridSource, /facet === 'notes' \|\| isGlobalSearching/);
  assert.match(workspaceSource, /const MANAGE_SEARCH_DEBOUNCE_MS = 180/);
  assert.match(workspaceSource, /notesStore\.searchNotes\(query, \{ scope: 'all' \}\)/);
  assert.match(workspaceSource, /localManageNoteSearch[\s\S]*?note\.tags[\s\S]*?notebookNameForSearchResult/);
  assert.match(workspaceSource, /manageGridRef\.value\?\.selectNotebook\?\.\(notebook\.id\)/);
  assert.match(gridSource, /defineExpose\(\{ selectNotebook \}\)/);
  assert.match(workspaceSource, /\.notes-ws__manage-search\s*\{[\s\S]*?left:\s*50%[\s\S]*?width:\s*clamp\(300px, 34vw, 520px\)/);
  assert.match(workspaceSource, /\.notes-ws__manage-search\s*\{[\s\S]*?height:\s*38px[\s\S]*?box-shadow:/);
  assert.match(workspaceSource, /\.notes-ws__manage-search\s*>\s*\.v-icon\s*\{[\s\S]*?var\(--pm-accent/);
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

test('note cards keep a fixed height and scroll excess tags in the compact editor', () => {
  assert.match(gridSource, /\.nmg__grid\s*\{[\s\S]*?align-items:\s*start;/);
  assert.match(gridSource, /\.nmg-card\s*\{[\s\S]*?height:\s*207px;/);
  assert.match(gridSource, /<NoteTagBar[\s\S]*?compact[\s\S]*?single-line/);
  assert.match(gridSource, /\.nmg-card__foot\s*\{[\s\S]*?height:\s*49px;/);
  assert.match(inlineTagEditorSource, /\.pm-tags-input--single-line\s*\{[\s\S]*?flex-flow:\s*row nowrap;[\s\S]*?overflow-x:\s*auto;/);
});

test('used note tags filter the grid from a dedicated right sidebar', () => {
  assert.match(gridSource, /<aside[\s\S]*?v-if="facet === 'notes' \|\| isGlobalSearching"[\s\S]*?class="nmg__tag-sidebar"/);
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
  // Die Seitenleiste ist jetzt ein „Filter"-Panel mit zwei Sektionen
  // (Notizbücher + Tags); der frühere reine „Tags"-Titel entfällt.
  assert.match(gridSource, /<h2 class="nmg__tag-sidebar-title">Filter<\/h2>/);
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

test('management cards keep editable tags in a separate footer', () => {
  assert.match(gridSource, /class="nmg-card__foot"[\s\S]*?<NoteTagBar[\s\S]*?compact/);
  assert.match(gridSource, /class="nmg-card__preview"[\s\S]*?class="nmg-card__snippet"/);
  assert.match(gridSource, /@update:tag-ids="\(ids\) => applyCardTags\(note, ids\)"/);
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

test('each note card exposes its own named actions without multi-selection', () => {
  for (const label of ['Als Vorlage speichern', 'In Papierkorb']) {
    assert.ok(gridSource.includes(`aria-label="${label}"`));
  }
  assert.match(gridSource, /@click="saveNoteAsTemplate\(note\)"/);
  assert.match(gridSource, /@click="trashNote\(note\)"/);
  assert.doesNotMatch(gridSource, /nmg__bulkbar|selectedIds|selectAllVisible|type="checkbox"|is-selected/);
  // Der redundante Stift-Button entfällt: Umbenennen läuft über den Titelklick.
  assert.doesNotMatch(gridSource, /aria-label="Umbenennen"/);
  assert.doesNotMatch(gridSource, /class="nmg-card__act"[^>]*@click="startRename\(note\)"/);
});

test('empty notes offer creation while empty searches show search feedback', () => {
  assert.match(gridSource, /!visibleItems.length && normalizedQuery[\s\S]*?<PmEmptyState/);
  assert.match(gridSource, /<GhostAddCard[\s\S]*?@click="\$emit\('create-note'\)"/);
  assert.match(gridSource, /<Vorlagenmappe[\s\S]*?facet === 'templates'/);
});

test('both template groups always expose creation through a placeholder card', () => {
  assert.doesNotMatch(templatesFolderSource, /class="vm__new"/);
  assert.doesNotMatch(templatesFolderSource, /\.vm__new\s*\{/);
  assert.match(templatesFolderSource, /:class="\{ 'vm__grid--ghost': !blockTemplates\.length \}"[\s\S]*?<VorlagenCard[\s\S]*?<GhostAddCard[\s\S]*?@click="openCreateBlock"/);
  assert.match(templatesFolderSource, /:class="\{ 'vm__grid--ghost': !startnotizen\.length \}"[\s\S]*?<VorlagenCard[\s\S]*?<GhostAddCard[\s\S]*?@click="createStartnotiz"/);
  assert.match(templatesFolderSource, /:title="blockTemplates\.length \? 'Neuer Schnellblock' : 'Noch kein Schnellblock'"/);
  assert.match(templatesFolderSource, /:title="startnotizen\.length \? 'Neue Startnotiz' : 'Noch keine Startnotiz'"/);
});

test('quick-block preview cards omit the redundant slash badge', () => {
  assert.doesNotMatch(templateCardSource, /class="vk__slash"/);
  assert.doesNotMatch(templateCardSource, /\.vk__slash\s*\{/);
  assert.doesNotMatch(templateCardSource, /Per \/ einfügbar/);
});

test('compact notes share document-row tokens and management cards use the content surface', () => {
  for (const token of [
    '--pm-document-row-bg',
    '--pm-document-row-border',
    '--pm-document-row-shadow',
    '--pm-document-row-hover-border',
  ]) {
    assert.match(themeSource, new RegExp(token));
    assert.match(documentsWorkspaceSource, new RegExp(`var\\(${token}`));
    assert.match(workspaceSource, new RegExp(`var\\(${token}`));

  }
  assert.match(gridSource, /\.nmg-card \{[\s\S]*?background: var\(--pm-content-surface/);
});

test('the management grid fades content without animating its dimensions', () => {
  assert.match(
    gridSource,
    /\.nmg__scroll\s*\{[\s\S]*?position:\s*relative;/,
  );
  assert.match(
    gridSource,
    /\.nmg__grid\s*\{[\s\S]*?display:\s*grid;[\s\S]*?align-content:\s*start;/,
  );
  assert.match(gridSource, /<Transition name="nmg-content" mode="out-in">/);
  assert.match(gridSource, /\.nmg-content-enter-active,[\s\S]*?transition:\s*opacity 150ms ease, transform 170ms/);
  assert.doesNotMatch(gridSource, /\.nmg-content-(?:enter|leave)-active\s*\{[^}]*?(?:height|width|max-height|padding):/);
});

test('notebooks add a flat filing facet to the manage sidebar', () => {
  // Eigene Sektion „Notizbücher" mit Anlegen-Button in der Filter-Seitenleiste.
  assert.match(gridSource, /nmg__filter-section[\s\S]*?Notizbücher/);
  assert.match(gridSource, /@click="startCreateNotebook"/);
  // Genau eine Facette aktiv: 'all' | <id> | 'none' (Ohne Notizbuch).
  assert.match(gridSource, /const activeNotebookId = ref\('all'\)/);
  // Facetten-Umschaltung passiert im Template (ohne `.value`).
  assert.match(gridSource, /@click="activeNotebookId = 'all'"/);
  assert.match(gridSource, /@click="activeNotebookId = 'none'"/);
  assert.match(gridSource, /Ohne Notizbuch/);
  // Lokaler Filter über note.notebook_id (Server liefert notebook_id im Item).
  assert.match(
    gridSource,
    /activeNotebookId\.value === 'none'[\s\S]*?items = items\.filter\(\(n\) => !n\.notebook_id\)/,
  );
  assert.match(
    gridSource,
    /items = items\.filter\(\(n\) => n\.notebook_id === activeNotebookId\.value\)/,
  );
  // Notizbücher werden aus dem Store bezogen und beim Mount geladen.
  assert.match(gridSource, /const notebooks = computed\(\(\) => notesStore\.notebooks\)/);
  assert.match(gridSource, /notesStore\.ensureNotebooksLoaded\(\)/);
});

test('management sorting lives in the right filter sidebar instead of above the cards', () => {
  assert.match(
    gridSource,
    /class="nmg__tag-sidebar"[\s\S]*?aria-label="Sortierung"[\s\S]*?class="nmg__sort-btn"[\s\S]*?\{\{ sortLabel \}\}/,
  );
  assert.doesNotMatch(gridSource, /class="nmg__toolbar"/);
  assert.match(gridSource, /\.nmg__sort-btn\s*\{[\s\S]*?width:\s*100%;/);
  assert.match(gridSource, /\.nmg__groups\s*\{[\s\S]*?padding:\s*22px 26px 28px/);
});

test('management cards can move a note into a notebook', () => {
  assert.match(gridSource, /title="In Notizbuch verschieben"/);
  assert.match(gridSource, /@click="moveNoteToNotebook\(note, nb\.id\)"/);
  assert.match(gridSource, /@click="moveNoteToNotebook\(note, null\)"/);
  assert.match(gridSource, /await notesStore\.moveToNotebook\(\[note\.id\], notebookId\)/);
});

test('notebooks can be created, renamed and deleted from the sidebar', () => {
  assert.match(gridSource, /await notesStore\.createNotebook\(\{ name \}\)/);
  assert.match(gridSource, /await notesStore\.updateNotebook\(nb\.id, \{ name \}\)/);
  assert.match(gridSource, /await notesStore\.deleteNotebook\(nb\.id\)/);
  // Löschen ist bewusst nicht destruktiv für die enthaltenen Notizen.
  assert.match(gridSource, /bleiben erhalten und liegen danach in keinem Notizbuch/);
});

test('the card title is editable with a direct click, like tags', () => {
  // Klick auf den Titel startet die Umbenennung direkt (stoppt das Öffnen).
  assert.match(
    gridSource,
    /class="nmg-card__title"[\s\S]*?@click\.stop="startRename\(note\)"[\s\S]*?@keydown\.enter\.stop\.prevent="startRename\(note\)"/,
  );
  // Hover-Affordance: der Titel signalisiert Editierbarkeit.
  assert.match(gridSource, /\.nmg-card__title\s*\{[\s\S]*?cursor:\s*text/);
  assert.match(gridSource, /\.nmg-card__title:hover\s*\{/);
});

test('each card shows its notebook membership as a filter chip', () => {
  assert.match(gridSource, /v-if="notebookFor\(note\)"[\s\S]*?class="nmg-card__notebook"/);
  assert.match(gridSource, /notebookFor\(note\)\.name/);
  assert.match(gridSource, /@click\.stop="filterByNotebook\(note\.notebook_id\)"/);
  // Auflösung Notiz→Notizbuch über eine Map (nicht linear je Karte).
  assert.match(gridSource, /const notebooksById = computed/);
  assert.match(gridSource, /function notebookFor\(note\)/);
  assert.match(gridSource, /function filterByNotebook\(notebookId\)[\s\S]*?activeNotebookId\.value = notebookId/);
});

test('renaming a notebook uses a standalone input, not one nested in a button', () => {
  // Regression: ein <input> im <button> schluckt Fokus/Tastatur (Eingabe unsichtbar).
  assert.match(gridSource, /v-if="editingNotebookId === nb\.id" class="nmg__nb-editing"/);
  assert.match(
    gridSource,
    /class="nmg__nb-editing"[\s\S]*?<input[\s\S]*?ref="notebookInputRef"[\s\S]*?<\/div>/,
  );
  // Der Chip-Button rendert im Edit-Modus NICHT (v-else) und trägt selbst kein input.
  assert.match(gridSource, /<template v-else>[\s\S]*?class="nmg__tag-cloud-chip nmg__nb-chip"/);
  assert.match(gridSource, /nmg__nb-chip"[\s\S]*?<span class="nmg__nb-name-text">\{\{ nb\.name \}\}<\/span>/);
  // Lesekontrast: Bearbeitungszeile hat eigene Textfarbe (nicht die Aktiv-Weißschrift).
  assert.match(gridSource, /\.nmg__nb-editing\s*\{[\s\S]*?color:\s*var\(--pm-text/);
});

test('the favorite star sits in the hover action menu with the document-style animation', () => {
  // Stern liegt im Aktionsmenü (nicht als separater Dauer-Button).
  assert.match(gridSource, /class="nmg-card__actions"[\s\S]*?nmg-card__act nmg-card__act--fav/);
  assert.match(gridSource, /@click="toggleFavorite\(note\)"/);
  assert.match(gridSource, /note\.is_favorite \? 'mdi-star' : 'mdi-star-outline'/);
  // Gold-Aktivfarbe + Pop/Ring-Animation wie die Dokumentenkarte.
  assert.match(gridSource, /\.nmg-card__act--fav\.is-active\s*\{[\s\S]*?var\(--pm-star/);
  assert.match(gridSource, /nmg-card__fav-wrap--pop/);
  assert.match(gridSource, /@keyframes nmg-fav-star-pop/);
  assert.match(gridSource, /@keyframes nmg-fav-star-ring/);
  // Animation nur beim aktiven Setzen (wie DocumentListPanel).
  assert.match(gridSource, /if \(next\) \{[\s\S]*?animatingFavoriteId\.value = note\.id/);
  // Favoriten stehen als eigene Gruppe oben.
  assert.match(gridSource, /favorites: 'Favoriten'/);
  assert.match(gridSource, /if \(note\.is_favorite\) return 'favorites'/);
});

test('favorite notes use the document list and open a read-only preview', () => {
  assert.doesNotMatch(documentsWorkspaceSource, /<FavoriteNotesSection/);
  assert.match(documentsWorkspaceSource, /:favorite-notes="visibleFavoriteNotes"/);
  assert.match(documentsWorkspaceSource, /@select-note="isTrashView \? selectTrashNote\(\$event\) : selectFavoriteNote\(\$event\)"/);
  assert.match(documentsWorkspaceSource, /<NotePreview :note-id="isTrashView \? selectedTrashNoteId : selectedFavoriteNoteId"/);
  assert.match(documentsWorkspaceSource, /async function selectDocument[^]*?selectedFavoriteNoteId.value = null/);
});

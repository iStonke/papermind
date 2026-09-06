import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const workspaceSource = await readFile(
  new URL('../src/views/NotesWorkspace.vue', import.meta.url),
  'utf8',
);
const documentsWorkspaceSource = await readFile(
  new URL('../src/views/DocumentsWorkspace.vue', import.meta.url),
  'utf8',
);
const dossierWorkspaceSource = await readFile(
  new URL('../src/views/DossierWorkspace.vue', import.meta.url),
  'utf8',
);
const notesDevHarnessSource = await readFile(
  new URL('../src/views/NotesDevHarness.vue', import.meta.url),
  'utf8',
);
const notesManageGridSource = await readFile(
  new URL('../src/components/notes/NotesManageGrid.vue', import.meta.url),
  'utf8',
);
const workspaceEditorSource = await readFile(
  new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url),
  'utf8',
);
const editorIllustrationSource = await readFile(
  new URL('../src/components/notes/NotesEditorIllustration.vue', import.meta.url),
  'utf8',
);
const noteEditorSource = await readNoteEditorSource();
const notePreviewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const noteVersionHistorySource = await readFile(
  new URL('../src/components/notes/NoteVersionHistoryDialog.vue', import.meta.url),
  'utf8',
);
const templateBoxViewSource = await readFile(
  new URL('../src/components/notes/nodes/TemplateBoxView.vue', import.meta.url),
  'utf8',
);
const baseDialogSource = await readFile(
  new URL('../src/components/BaseDialog.vue', import.meta.url),
  'utf8',
);
const documentListPanelSource = await readFile(
  new URL('../src/components/DocumentListPanel.vue', import.meta.url),
  'utf8',
);
const listActionToolbarSource = await readFile(
  new URL('../src/components/ListActionToolbar.vue', import.meta.url),
  'utf8',
);
const notesApiSource = await readFile(
  new URL('../src/api/notes.js', import.meta.url),
  'utf8',
);
const notesStoreSource = await readFile(
  new URL('../src/stores/notes.js', import.meta.url),
  'utf8',
);
const templateStart = workspaceSource.indexOf('<template>');
const templateEnd = workspaceSource.indexOf('<script setup>', templateStart);
const templateSource = workspaceSource.slice(templateStart, templateEnd);

test('notes workspace reserves a compact list and a separate editor area', () => {
  assert.match(templateSource, /notes-ws__list-panel/);
  assert.match(templateSource, /notes-ws__editor-slot/);
  assert.match(templateSource, /<NoteWorkspaceEditor/);
  assert.match(workspaceSource, /--notes-list-width:\s*clamp\(300px, 31vw, 380px\)/);
  assert.match(workspaceSource, /\.notes-ws\s*\{[\s\S]*?display:\s*flex/);
});

test('notes list slides in and out while the editor keeps the toggle accessible', () => {
  assert.match(templateSource, /'is-list-collapsed': isListPanelCollapsed/);
  assert.match(templateSource, /:inert="panelInert"/);
  assert.match(workspaceSource, /panelInert = computed\(\(\) => isListPanelCollapsed\.value \|\| isManageMode\.value\)/);
  assert.match(templateSource, /@toggle-list="toggleNotesList"/);
  assert.match(templateSource, /<NoteWorkspaceEditor[\s\S]*?v-if="activeNote"/);
  assert.match(templateSource, /v-if="!activeNote && isListPanelCollapsed"[\s\S]*?mdi-arrow-collapse/);
  assert.match(templateSource, /<NotesEditorIllustration[\s\S]*?v-if="!activeNote"/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__list-toggle"/);
  assert.match(workspaceEditorSource, /listVisible \? 'fullscreen' : 'fullscreen-exit'/);
  assert.match(workspaceEditorSource, /listVisible \? 'Editor im Vollbild anzeigen' : 'Vollbildansicht verlassen'/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__list-toggle"[\s\S]*?<v-menu/);
  assert.match(workspaceEditorSource, /emit\('toggle-list'\)/);
  assert.match(workspaceSource, /margin-left:\s*calc\(-1 \* var\(--notes-list-width\)\)/);
  assert.match(workspaceSource, /transform:\s*translateX\(-18px\)/);
  assert.match(workspaceSource, /localStorage\.setItem\('pm-notes-list-collapsed'/);
  assert.match(workspaceSource, /prefers-reduced-motion:\s*reduce[\s\S]*notes-ws__list-panel/);
  assert.match(workspaceSource, /pm-no-animations[\s\S]*notes-ws__list-panel/);
});

test('manage mode uses the vertical reader transition without resizing its content', () => {
  assert.match(templateSource, /<Transition name="notes-ws-manage" appear>[\s\S]*?v-if="isManageMode"[\s\S]*?class="notes-ws__manage-panel"/);
  assert.match(templateSource, /class="notes-ws__manage-panel"[\s\S]*?<NotesManageGrid/);
  assert.match(templateSource, /aria-label="Verwaltung schließen"[\s\S]*?<v-icon size="20">mdi-close<\/v-icon>/);
  assert.match(templateSource, /class="notes-ws__editor-slot"[\s\S]*?:inert="isManageMode"/);
  assert.match(workspaceSource, /\.notes-ws__manage-panel\s*{[\s\S]*?position:\s*absolute;[\s\S]*?inset:\s*0;[\s\S]*?overflow:\s*hidden/);
  assert.match(workspaceSource, /\.notes-ws__manage-panel\s*{[\s\S]*?z-index:\s*100/);
  assert.match(noteEditorSource, /\.note-editor__toolbar-guard\s*{[\s\S]*?z-index:\s*12/);
  assert.match(workspaceSource, /\.notes-ws-manage-enter-active\s*{[\s\S]*?transition:\s*transform 460ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/);
  assert.match(workspaceSource, /\.notes-ws-manage-leave-active\s*{[\s\S]*?transition:\s*transform 620ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/);
  assert.match(workspaceSource, /\.notes-ws-manage-enter-from,[\s\S]*?\.notes-ws-manage-leave-to\s*{[\s\S]*?transform:\s*translateY\(100%\)/);
  assert.match(workspaceSource, /\.notes-ws-manage-enter-to,[\s\S]*?\.notes-ws-manage-leave-from\s*{[\s\S]*?transform:\s*translateY\(0\)/);
  assert.doesNotMatch(workspaceSource, /\.notes-ws\.is-manage\s*{[\s\S]*?--notes-list-width:\s*100%/);
  assert.doesNotMatch(workspaceSource, /--notes-manage-content-width|ResizeObserver|MANAGE_TRANSITION_DURATION_MS|notes-ws-manage-slide/);
});

test('notes management remembers the selected facet across closing and reloads', () => {
  assert.match(workspaceSource, /NOTES_MANAGE_FACET_STORAGE_KEY = 'pm-notes-manage-facet-v1'/);
  assert.match(workspaceSource, /const manageFacet = ref\(loadManageFacet\(\)\)/);
  assert.match(
    workspaceSource,
    /function loadManageFacet\(\)[\s\S]*?localStorage\.getItem\(NOTES_MANAGE_FACET_STORAGE_KEY\)[\s\S]*?return 'notes'/,
  );
  assert.match(
    workspaceSource,
    /function persistManageFacet\(value\)[\s\S]*?localStorage\.setItem\(NOTES_MANAGE_FACET_STORAGE_KEY, normalizeManageFacet\(value\)\)/,
  );
  assert.match(workspaceSource, /watch\(manageFacet, persistManageFacet\)/);
  assert.match(workspaceSource, /value === 'templates' \? 'templates' : 'notes'/);
});

test('the notes heading shows the notebook selected in either notes view', () => {
  assert.match(templateSource, /<span>Notizen<\/span>[\s\S]*?v-if="activeNotebookHeading"[\s\S]*?>·<\/span>/);
  assert.match(templateSource, /manageFacet === 'notes' && manageNotebookHeading[\s\S]*?>·<\/span>[\s\S]*?\{\{ manageNotebookHeading \}\}/);
  assert.match(templateSource, /@notebook-selection-change="manageNotebookHeading = \$event"/);
  assert.match(notesManageGridSource, /'notebook-selection-change'/);
  assert.match(notesManageGridSource, /const activeNotebookLabel = computed\(\(\) => \{[\s\S]*?activeNotebookId\.value === 'none'[\s\S]*?'Ohne Notizbuch'[\s\S]*?\.name \|\| ''/);
  assert.match(notesManageGridSource, /watch\([\s\S]*?activeNotebookLabel,[\s\S]*?emit\('notebook-selection-change', label\)[\s\S]*?immediate: true/);
});

test('notes list follows the shared title, toolbar, and row hierarchy', () => {
  assert.match(templateSource, /<span>Notizen<\/span>/);
  assert.match(templateSource, /v-if="activeNotebookHeading"[\s\S]*?notes-ws__heading-separator[\s\S]*?>·<\/span>[\s\S]*?\{\{ activeNotebookHeading \}\}/);
  assert.match(workspaceSource, /const activeNotebookHeading = computed\(\(\) => \([\s\S]*?notebookFilter\.value \? notebookFilterLabel\.value : ''/);
  assert.match(workspaceSource, /\.notes-ws__heading-context\s*\{[\s\S]*?text-overflow:\s*ellipsis/);
  assert.match(templateSource, /Neue Notiz/);
  assert.match(templateSource, /<ListActionToolbar/);
  assert.match(templateSource, /:actions="toolbarActions"/);
  assert.match(templateSource, /:show-selection="false"/);
  assert.match(templateSource, /notes-ws__item-snippet/);
  assert.match(workspaceSource, /notes-ws__item\.is-active/);
  const compactListTemplate = templateSource.slice(0, templateSource.indexOf('<Transition name="notes-ws-manage"'));
  assert.doesNotMatch(compactListTemplate, /<v-text-field|type="search"|notes-ws__toggle/);
});

test('notes list is grouped by creation day with compact sticky headers', () => {
  assert.match(templateSource, /v-for="group in groupedNotes"/);
  assert.match(templateSource, /class="notes-ws__group-heading"/);
  assert.match(templateSource, /v-for="note in group\.notes"/);
  assert.match(workspaceSource, /groupNotesByCreationDay\(visibleNotes\.value\)/);
  assert.match(workspaceSource, /\.notes-ws__group-heading\s*\{[\s\S]*?position:\s*sticky[\s\S]*?top:\s*0/);
  assert.doesNotMatch(templateSource, /notes-ws__group-count/);
});

test('notes toolbar offers the standard sort and date-range menus', () => {
  assert.match(workspaceSource, /key:\s*'sort'/);
  assert.match(workspaceSource, /key:\s*'dateRange'/);
  assert.match(workspaceSource, /mdi-sort/);
  assert.match(workspaceSource, /mdi-calendar-range/);
  assert.match(workspaceSource, /value:\s*'updated'[\s\S]*?value:\s*'created'[\s\S]*?value:\s*'title'/);
  assert.match(workspaceSource, /created_at \|\| b\.updated_at/);
});

test('empty notes reuse the shared animated placeholder without a second create action', () => {
  assert.match(templateSource, /<PmEmptyState/);
  assert.match(templateSource, /icon="mdi-note-outline"/);
  assert.doesNotMatch(templateSource, /Erste Notiz anlegen/);
});

test('notes loading errors reuse the centered empty-state language with a quiet retry action', () => {
  assert.match(
    templateSource,
    /v-else-if="loadError"[\s\S]*?notes-ws__empty-state-wrap--error[\s\S]*?<PmEmptyState[\s\S]*?icon="mdi-alert-circle-outline"[\s\S]*?:title="loadError"[\s\S]*?:animated="false"/,
  );
  assert.match(templateSource, /subtitle="Prüfe deine Verbindung und versuche es erneut\."/);
  assert.match(templateSource, /class="notes-ws__retry"[\s\S]*?mdi-refresh[\s\S]*?Erneut versuchen/);
  assert.doesNotMatch(templateSource, /notes-ws__state--error/);
  assert.match(workspaceSource, /\.notes-ws__empty-state-wrap\s*\{[\s\S]*?width:\s*100%;[\s\S]*?height:\s*100%;[\s\S]*?align-items:\s*center;[\s\S]*?justify-content:\s*center/);
  assert.match(workspaceSource, /\.notes-ws__empty-state-wrap--error :deep\(\.pm-empty-state__halo\)\s*\{[\s\S]*?var\(--pm-danger/);
  assert.match(workspaceSource, /\.notes-ws__retry\s*\{[\s\S]*?height:\s*34px[\s\S]*?border-radius:\s*999px/);
  assert.doesNotMatch(workspaceSource, /\.notes-ws__retry:hover[^{]*\{[^}]*transform:/);
});

test('empty editor uses a generous note illustration instead of a second placeholder', () => {
  assert.match(templateSource, /<NotesEditorIllustration[\s\S]*?v-if="!activeNote"/);
  assert.doesNotMatch(templateSource, /<PmEmptyState\s+v-if="!activeNote"/);
  assert.match(editorIllustrationSource, /<svg[\s\S]*?viewBox="0 0 560 360"/);
  assert.match(editorIllustrationSource, /class="notes-editor-illustration__sheet-outline"/);
  assert.match(editorIllustrationSource, /class="notes-editor-illustration__sheet-echo"/);
  assert.match(editorIllustrationSource, /class="notes-editor-illustration__flourish"/);
  assert.doesNotMatch(editorIllustrationSource, /drop-shadow|filter:\s*blur|infinite/);
  assert.match(editorIllustrationSource, /role="status"[\s\S]*?aria-label="Keine Notiz ausgewählt/);
  assert.match(editorIllustrationSource, /prefers-reduced-motion:\s*reduce/);
  assert.match(editorIllustrationSource, /:global\(\.pm-no-animations\)/);
});

test('global note preferences control list mode, typography, and spellcheck', () => {
  assert.match(workspaceSource, /settingsDraft\.ui\.notes_default_view/);
  assert.match(workspaceSource, /mode === 'list'[\s\S]*?mode === 'focus'[\s\S]*?loadNotesListCollapsed/);
  assert.match(workspaceSource, /settingsDraft\.ui\.notes_sort_order/);
  assert.match(workspaceEditorSource, /:writing-width="notesWritingWidth"/);
  assert.match(workspaceEditorSource, /:paragraph-spacing="notesParagraphSpacing"/);
  assert.match(workspaceEditorSource, /:font-family="notesFontFamily"/);
  assert.match(workspaceEditorSource, /:spellcheck-enabled="notesSpellcheckEnabled"/);
  assert.match(noteEditorSource, /note-editor--width-compact[\s\S]*?max-width:\s*58ch/);
  assert.match(noteEditorSource, /note-editor--width-comfortable[\s\S]*?max-width:\s*76ch/);
  assert.match(noteEditorSource, /note-editor--width-wide[\s\S]*?max-width:\s*92ch/);
  assert.match(noteEditorSource, /note-editor--spacing-compact[\s\S]*?--note-editor-paragraph-gap:\s*0\.3em/);
  assert.match(noteEditorSource, /note-editor--spacing-spacious[\s\S]*?--note-editor-paragraph-gap:\s*0\.75em/);
  assert.match(noteEditorSource, /note-editor--font-serif[\s\S]*?--note-editor-font-family:\s*Georgia/);
  assert.match(noteEditorSource, /note-editor--font-mono[\s\S]*?--note-editor-font-family:\s*ui-monospace/);
  assert.match(noteEditorSource, /\.pm-content h[12]\)[\s\S]*?font-family:\s*inherit/);
  assert.match(noteEditorSource, /setAttribute\('spellcheck', enabled \? 'true' : 'false'\)/);
});

test('a plain Enter advances by one controlled paragraph step', () => {
  assert.match(noteEditorSource, /--note-editor-paragraph-gap:\s*0\.5em/);
  assert.match(noteEditorSource, /\.pm-content > \*\)\s*\{[\s\S]*?margin-block:\s*0/);
  assert.match(noteEditorSource, /\.pm-content > \* \+ \*\)\s*\{\s*margin-top:\s*var\(--note-editor-paragraph-gap\)/);
  assert.match(notePreviewSource, /--note-preview-paragraph-gap:\s*0\.25em/);
  assert.match(notePreviewSource, /\.pm-content > \*\)\s*\{\s*margin-block:\s*0/);
  assert.doesNotMatch(noteEditorSource, /--note-editor-paragraph-gap:\s*1\.05em/);
});

test('all structural editor elements share a generous vertical rhythm', () => {
  assert.match(noteEditorSource, /--note-editor-block-gap:\s*1\.75rem/);
  assert.match(noteEditorSource, /note-editor--spacing-compact[\s\S]*?--note-editor-block-gap:\s*1\.25rem/);
  assert.match(noteEditorSource, /note-editor--spacing-spacious[\s\S]*?--note-editor-block-gap:\s*2\.1rem/);
  assert.match(noteEditorSource, /\.pm-content > \* \+ :not\(p\)\)[\s\S]*?\.pm-content > :not\(p\) \+ \*\)[\s\S]*?margin-top:\s*var\(--note-editor-block-gap\)/);
  assert.match(noteEditorSource, /\[data-layout-column\] > \* \+ :not\(p\)\)[\s\S]*?\[data-layout-column\] > :not\(p\) \+ \*\)[\s\S]*?margin-top:\s*var\(--note-editor-block-gap\)/);
  assert.match(noteEditorSource, /\.pm-content hr\)[\s\S]*?margin-inline:\s*0/);
  assert.doesNotMatch(noteEditorSource, /\.pm-content hr\)[\s\S]*?margin:\s*1\.4em 0/);
});

test('all heading levels use the same restrained spacing beside any element', () => {
  assert.match(noteEditorSource, /--note-editor-heading-gap:\s*0\.75rem/);
  assert.match(noteEditorSource, /\.pm-content > \* \+ :is\(h1, h2, h3, h4, h5, h6\)\)[\s\S]*?\.pm-content > :is\(h1, h2, h3, h4, h5, h6\) \+ \*[\s\S]*?margin-top:\s*var\(--note-editor-heading-gap\)/);
  assert.match(noteEditorSource, /\[data-layout-column\] > \* \+ :is\(h1, h2, h3, h4, h5, h6\)\)[\s\S]*?\[data-layout-column\] > :is\(h1, h2, h3, h4, h5, h6\) \+ \*[\s\S]*?margin-top:\s*var\(--note-editor-heading-gap\)/);
  assert.match(noteEditorSource, /\.pm-content > :is\(h1, h2, h3, h4, h5, h6\):first-child[\s\S]*?margin-top:\s*0/);
  assert.doesNotMatch(noteEditorSource, /\.pm-content h[1-6]\)[^}]*margin-top:/);
});

test('new-note action exists only inside the notes workspace', () => {
  assert.match(templateSource, /Neue Notiz/);
  assert.match(templateSource, /v-if="!loadError"[\s\S]*?class="notes-ws__fab"/);
  assert.match(templateSource, /class="notes-ws__fab-main"[\s\S]*?color="primary"/);
  assert.match(templateSource, /<v-icon size="20" class="mr-1">mdi-square-edit-outline<\/v-icon>/);
  assert.match(templateSource, /:class="\{ 'has-templates': notesStore\.templates\.length > 0 \}"/);
  assert.match(templateSource, /<v-menu[\s\S]*?v-if="notesStore\.templates\.length"[\s\S]*?class="notes-ws__fab-caret"/);
  assert.doesNotMatch(templateSource, /notes-ws__template-pop-empty|Noch keine Vorlagen/);
  assert.match(workspaceSource, /\.notes-ws__fab-main\.v-btn\s*\{[\s\S]*?border-radius:\s*999px;/);
  assert.match(workspaceSource, /\.notes-ws__fab\.has-templates \.notes-ws__fab-main\.v-btn\s*\{[\s\S]*?border-radius:\s*999px 0 0 999px;/);
  assert.match(workspaceSource, /\.notes-ws__fab \.v-btn:hover:not\(\.v-btn--disabled\)\s*\{[\s\S]*?background-color:\s*color-mix/);
  assert.match(workspaceSource, /\.notes-ws__fab:has\(\.v-btn:hover:not\(\.v-btn--disabled\)\)\s*\{[\s\S]*?box-shadow:/);
  assert.doesNotMatch(workspaceSource, /\.notes-ws__fab \.v-btn:hover:not\(\.v-btn--disabled\)\s*\{[^}]*transform:/);
  assert.doesNotMatch(templateSource, /density="comfortable"/);
  assert.doesNotMatch(documentsWorkspaceSource, /aria-label="Neue Notiz erstellen"/);
  assert.doesNotMatch(documentsWorkspaceSource, />\s*Neue Notiz\s*<\/v-btn>/);
});

test('new notes enter the list with a dedicated reduced-motion-safe animation', () => {
  assert.match(templateSource, /'is-new': note\.id === newlyCreatedNoteId/);
  assert.match(workspaceSource, /@keyframes notes-ws-note-created/);
  assert.match(workspaceSource, /finishNewNoteAnimation\(note\.id\)/);
  assert.match(workspaceSource, /pm-no-animations[\s\S]*notes-ws__item\.is-new/);
  assert.match(workspaceSource, /prefers-reduced-motion:\s*reduce[\s\S]*notes-ws__item\.is-new/);
});

test('new notes put the caret directly into the writable editor body', () => {
  assert.match(workspaceSource, /async function revealNewNote\(note, cursorPosition = 'start'\)/);
  assert.match(workspaceSource, /async function focusRequestedEditorBody\(cursorPosition\)[\s\S]*?await nextTick\(\)[\s\S]*?focusEditorBody\?\.\(cursorPosition\)/);
  assert.match(workspaceSource, /revealNewNote\(await notesStore\.createFromTemplate\(templateId\), 'end'\)/);
  assert.match(notesStoreSource, /pendingOpenCursorPosition/);
  assert.match(documentsWorkspaceSource, /openLinkedNoteInWorkspace\(note\.id, \{ cursorPosition: 'end' \}\)/);
  assert.match(dossierWorkspaceSource, /openDossierNoteInWorkspace\(note\.id, \{ cursorPosition: 'end' \}\)/);
  assert.match(notesManageGridSource, /emit\('open-note', note\.id, \{ cursorPosition: 'end' \}\)/);
  assert.match(notesDevHarnessSource, /focusBody\?\.\('start'\)/);
  assert.match(workspaceEditorSource, /pendingEditorFocusRequest = \{[\s\S]*?noteId: props\.noteId,[\s\S]*?position: normalizedPosition/);
  assert.match(workspaceEditorSource, /nextTick\(\(\) => flushPendingEditorFocus\(noteId\)\)/);
  assert.match(workspaceEditorSource, /function flushPendingEditorFocus\(noteId = loadedNoteId\.value\)[\s\S]*?focusBody\?\.\(request\.position\) === true/);
  assert.match(workspaceEditorSource, /defineExpose\(\{[\s\S]*?focusEditorBody/);
  assert.match(noteEditorSource, /position === 'start' \|\| position === 'end'[\s\S]*?focus\(position\)\.run\(\)[\s\S]*?return true/);
});

test('note navigation panel stays flat in light and dark mode', () => {
  const navigatorStyle = workspaceEditorSource.match(
    /\.note-workspace-editor__navigator\s*\{([\s\S]*?)\n\}/,
  )?.[1] || '';
  assert.doesNotMatch(navigatorStyle, /box-shadow/);
  assert.doesNotMatch(
    workspaceEditorSource,
    /v-theme--dark \.note-workspace-editor__navigator[\s\S]*?box-shadow/,
  );
});

test('removing a note reuses the document collapse timing before updating the list', () => {
  assert.match(workspaceSource, /NOTE_REMOVAL_DURATION_MS\s*=\s*210/);
  assert.match(workspaceSource, /notesStore\.trash\(note\.id\)[\s\S]*animateNoteRemoval\(note\.id\)[\s\S]*notesStore\.removeFromList\(note\.id\)/);
  assert.match(workspaceSource, /height 210ms[\s\S]*opacity 160ms[\s\S]*transform 180ms/);
  assert.match(documentListPanelSource, /height 210ms[\s\S]*opacity 160ms[\s\S]*transform 180ms/);
  assert.match(workspaceSource, /pm-no-animations[\s\S]*notes-ws__item\.is-removing/);
});

test('empty notes skip confirmation but enter the trash for undo', () => {
  assert.match(workspaceSource, /noteIsEmptyForDeletion\(note\)[\s\S]*discardEmptyNote\(note\)/);
  assert.match(
    workspaceSource,
    /notesStore\.trash\(note\.id\)[\s\S]*animateNoteRemoval\(note\.id\)[\s\S]*notesStore\.removeFromList\(note\.id\)/,
  );
  assert.match(workspaceEditorSource, /isNoteEmpty\(\{ title: title\.value, body_json: body\.value \}\)/);
  assert.match(workspaceEditorSource, /defineExpose\([\s\S]*isEmpty/);
  assert.match(notesApiSource, /apiDelete\(`\/api\/notes\/\$\{id\}`\)/);
  assert.match(notesStoreSource, /async function deletePermanently\(id\)/);
});

test('note deletion uses the PaperMind destructive dialog instead of browser confirmation', () => {
  assert.match(templateSource, /<DestructiveDialog/);
  assert.match(templateSource, /title="Notiz löschen"/);
  assert.match(templateSource, /primary-text="In Papierkorb"/);
  assert.match(templateSource, /@primary="confirmDeleteNote"/);
  assert.doesNotMatch(workspaceSource, /window\.confirm/);
});

test('notes use soft-delete endpoints and appear in the shared trash', () => {
  assert.match(notesApiSource, /api\/notes\/\$\{id\}\/trash/);
  assert.match(notesApiSource, /api\/notes\/\$\{id\}\/restore/);
  assert.match(notesApiSource, /apiDelete\('\/api\/notes\/trash'\)/);
  assert.match(notesStoreSource, /await trash\(id\)/);
  assert.match(documentListPanelSource, /isTrashView \? 'Gelöschte Notizen' : 'Favorisierte Notizen'/);
  assert.match(documentListPanelSource, /emit\('restore-note', note\)/);
  assert.match(documentsWorkspaceSource, /:trash-notes="visibleTrashedNotes"/);
  assert.match(documentsWorkspaceSource, /emptyNotesTrash\(\)/);
});

test('workspace editor keeps normal autosave quiet and exposes actionable sync problems', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__title"/);
  assert.match(workspaceEditorSource, /v-model="title"/);
  assert.match(workspaceEditorSource, /@keydown\.enter\.prevent="focusEditorBody"/);
  assert.match(workspaceEditorSource, /Dokument zuordnen/);
  assert.match(workspaceEditorSource, /v-else[\s\S]*?class="note-workspace-editor__doc-chip note-workspace-editor__doc-chip--empty"[\s\S]*?mdi-link-variant-plus/);
  assert.match(workspaceEditorSource, /v-if="syncIssueVisible"/);
  assert.match(workspaceEditorSource, /Nicht synchronisiert · lokal gesichert/);
  assert.match(workspaceEditorSource, /@click="retrySave"/);
  assert.match(workspaceEditorSource, /status === 'conflict'/);
  assert.match(workspaceEditorSource, /\['error', 'conflict', 'local'\]\.includes\(status\.value\)/);
  assert.doesNotMatch(workspaceEditorSource, /v-model:title="title"/);
  assert.match(noteEditorSource, /v-if="!workspace"[\s\S]*?class="note-editor__title"/);
  assert.doesNotMatch(noteEditorSource, /note-editor--workspace \.note-editor__title/);
  assert.doesNotMatch(workspaceEditorSource, /mdi-star-outline/);
  assert.doesNotMatch(workspaceEditorSource, /toggleFavorite/);
  assert.doesNotMatch(workspaceEditorSource, />Löschen<\/button>/);
  assert.doesNotMatch(templateSource, /@delete="removeNote\(activeNote\)"/);
  assert.match(workspaceEditorSource, /notesStore\.update/);
  assert.match(workspaceEditorSource, /setTimeout\([\s\S]*650/);
  assert.match(workspaceEditorSource, /base_revision: pipeline\.serverRevision/);
  assert.match(workspaceEditorSource, /window\.addEventListener\('beforeunload'/);
  assert.match(workspaceEditorSource, /:readonly="switching \|\| status === 'conflict'"/);
  assert.match(workspaceEditorSource, /:readonly="status === 'conflict'"/);
  assert.match(noteEditorSource, /editable: !props\.readonly/);
  assert.match(noteEditorSource, /setEditable\(!readonly\)/);
});

test('switching notes keeps editor chrome mounted and uses prefetched note details', () => {
  assert.doesNotMatch(templateSource, /<NoteWorkspaceEditor[\s\S]*?:key="activeNote\.id"/);
  assert.doesNotMatch(workspaceEditorSource, /<NoteEditor[\s\S]*?:key="noteId"/);
  assert.match(workspaceEditorSource, /loading && !hasLoadedContent/);
  assert.match(workspaceEditorSource, /loadError && !hasLoadedContent/);
  assert.match(workspaceEditorSource, /const cachedNote = notesStore\.peek\(noteId\)/);
  assert.match(workspaceEditorSource, /const noteId = loadedNoteId\.value/);
  assert.match(templateSource, /@pointerenter="prefetchNote\(note\.id\)"/);
  assert.match(workspaceSource, /await notesStore\.get\(noteId\)[\s\S]*?activeNoteId\.value = noteId/);
  assert.match(notesStoreSource, /const noteDetails = new Map\(\)/);
  assert.match(notesStoreSource, /function peek\(id\)/);
  assert.match(notesStoreSource, /detailRequests\.has\(id\)/);
  assert.match(notesStoreSource, /delete optimisticPatch\.base_revision/);
  assert.match(notesStoreSource, /delete optimisticPatch\.history_reason/);
  assert.match(notesStoreSource, /const optimisticDetail = previousDetail \? \{ \.\.\.previousDetail, \.\.\.optimisticPatch \} : null/);
});

test('editor scroll position is restored per note across switches and reloads', () => {
  assert.match(workspaceEditorSource, /ref="scrollContainerRef"[\s\S]*?@scroll\.passive="rememberScrollPosition\(\)"/);
  assert.match(workspaceEditorSource, /NOTE_SCROLL_POSITIONS_STORAGE_KEY\s*=\s*'pm-note-scroll-positions-v1'/);
  assert.match(workspaceEditorSource, /NOTE_SCROLL_POSITIONS_LIMIT\s*=\s*100/);
  assert.match(workspaceEditorSource, /rememberScrollPosition\(previousNoteId\)[\s\S]*?finalizeHistory\(previousNoteId, 'navigation'\)/);
  assert.match(workspaceEditorSource, /restoreScrollPosition\(noteId\)/);
  assert.match(workspaceEditorSource, /window\.localStorage\.setItem\([\s\S]*?NOTE_SCROLL_POSITIONS_STORAGE_KEY/);
  assert.match(noteEditorSource, /function restoreWorkspaceScroll\(top\)/);
  assert.match(noteEditorSource, /defineExpose\(\{[\s\S]*?restoreWorkspaceScroll,[\s\S]*?scrollToDocumentPosition,/);
  assert.match(noteEditorSource, /window\.requestAnimationFrame\([\s\S]*?scrollElement\.scrollTop = targetTop/);
});

test('the complete editor whitespace refocuses without moving the caret or scrolling', () => {
  assert.match(noteEditorSource, /@pointerdown="refocusEditorFromWhitespace"/);
  assert.match(noteEditorSource, /function refocusEditorFromWhitespace\(event\)/);
  assert.match(noteEditorSource, /target\.closest\('\.pm-float, button, input, select, textarea, a'\)/);
  assert.match(noteEditorSource, /content\.contains\(target\) && target !== content/);
  assert.match(noteEditorSource, /selection instanceof TextSelection && !selection\.empty/);
  assert.match(noteEditorSource, /chain\.setTextSelection\(selection\.head\)/);
  assert.match(noteEditorSource, /chain\.focus\(undefined, \{ scrollIntoView: false \}\)\.run\(\)/);
  assert.doesNotMatch(noteEditorSource, /ed\.chain\(\)\.focus\('end'\)\.run\(\)/);
  assert.match(noteEditorSource, /\.note-editor__surface\s*\{[\s\S]*?cursor:\s*text/);
});

test('linked documents use a compact header chip and the library picker pattern', () => {
  assert.match(workspaceEditorSource, /<\/div>\s*<span class="note-workspace-editor__meta-sep" aria-hidden="true" \/>\s*<v-menu\s*v-if="linkedDocument"/);
  assert.doesNotMatch(workspaceEditorSource, /v-if="linkedDocument" class="note-workspace-editor__meta-sep"/);
  assert.match(workspaceEditorSource, /--pm-note-placeholder-chip-border:\s*color-mix/);
  assert.match(workspaceEditorSource, /--pm-note-placeholder-chip-font-size:\s*12\.5px/);
  assert.match(workspaceEditorSource, /--pm-note-placeholder-chip-font-weight:\s*400/);
  assert.match(workspaceEditorSource, /--pm-note-placeholder-chip-letter-spacing:\s*0\.012em/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input\)\s*\{[\s\S]*?--pm-detail-chip-add-border:\s*var\(--pm-note-placeholder-chip-border\)/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input__add-label\)\s*\{[\s\S]*?font-size:\s*var\(--pm-note-placeholder-chip-font-size\);[\s\S]*?font-weight:\s*var\(--pm-note-placeholder-chip-font-weight\)/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__doc-chip--empty\s*\{[\s\S]*?height:\s*26px;[\s\S]*?border:\s*1px dashed var\(--pm-note-placeholder-chip-border\);[\s\S]*?font-size:\s*var\(--pm-note-placeholder-chip-font-size\);[\s\S]*?font-weight:\s*var\(--pm-note-placeholder-chip-font-weight\)/);
  assert.match(workspaceEditorSource, /v-if="linkedDocument"[\s\S]*?class="note-workspace-editor__doc-chip"/);
  assert.match(workspaceEditorSource, /note-workspace-editor__doc-chip-label/);
  assert.match(workspaceEditorSource, /title="Dokument öffnen"[\s\S]*?title="Dokument wechseln"[\s\S]*?title="Verknüpfung lösen"/);
  assert.match(workspaceEditorSource, /<BaseDialog[\s\S]*?title="Dokument zuordnen"[\s\S]*?PaperMind-Bibliothek[\s\S]*?max-width="780"[\s\S]*?scrollable/);
  assert.match(workspaceEditorSource, /placeholder="Dokumente suchen"/);
  assert.match(workspaceEditorSource, /v-for="document in documentPickerDocuments"[\s\S]*?documentThumbnailUrl\(document\.id\)/);
  assert.match(workspaceEditorSource, /documentPickerSearchTimer[\s\S]*?280/);
  assert.match(workspaceEditorSource, /useSettingsStore/);
  assert.match(workspaceEditorSource, /showFilenameSuffix/);
  assert.match(workspaceEditorSource, /formatDocumentFilename[\s\S]*?replace\(\/\\\.\[A-Za-z\]/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__doc-chip-label\s*\{[\s\S]*?text-overflow:\s*ellipsis/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__document-card/);
});

test('document assignment uses a compact stable chip without layout animation', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__doc-chip note-workspace-editor__doc-chip--empty"/);
  assert.match(workspaceEditorSource, /async function openDocumentPicker\(\)[\s\S]*?documentPickerOpen\.value = true/);
  assert.match(workspaceEditorSource, /function assignPickedDocument\(\)[\s\S]*?assignDocument\(documentPickerSelection\.value\)/);
  assert.match(workspaceEditorSource, /function assignDocument\(document\)[\s\S]*?patchBodyAttributes/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__doc-chip:hover\s*\{[\s\S]*?background:/);
  assert.match(workspaceEditorSource, /prefers-reduced-motion:\s*reduce[\s\S]*?\.note-workspace-editor__doc-chip \{ transition: none; \}/);
  assert.doesNotMatch(workspaceEditorSource, /pm-document-(?:action|link|chip)/);
});

test('document picker and its base dialog keep readable contrast in dark mode overlays', () => {
  const pickerStyles = workspaceEditorSource.slice(
    workspaceEditorSource.indexOf('.note-workspace-editor__picker-list'),
    workspaceEditorSource.indexOf('.note-workspace-editor__state'),
  );
  assert.match(baseDialogSource, /\.pm-dialog\s*\{[\s\S]*?color:\s*rgb\(var\(--v-theme-on-surface\)\)/);
  assert.match(baseDialogSource, /border:\s*1px solid rgba\(var\(--v-theme-on-surface\), 0\.12\)/);
  assert.match(pickerStyles, /color:\s*rgb\(var\(--v-theme-on-surface\)\)/);
  assert.match(pickerStyles, /color:\s*rgba\(var\(--v-theme-on-surface\), 0\.6\)/);
  assert.match(pickerStyles, /background:\s*rgba\(var\(--v-theme-primary\), 0\.12\)/);
  assert.doesNotMatch(pickerStyles, /var\(--pm-(?:text|muted|divider|row-hover|chip-bg)/);
});

test('note export and template actions live in the compact overflow menu', () => {
  const moreAction = workspaceEditorSource.indexOf('class="note-workspace-editor__more-btn"');
  const fullscreenAction = workspaceEditorSource.indexOf('class="note-workspace-editor__list-toggle"');
  assert.ok(fullscreenAction >= 0 && fullscreenAction < moreAction);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__view-divider/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__more-menu"/);
  assert.match(workspaceEditorSource, /location="bottom end" :offset="8" transition="fade-transition"/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__more-label">Aktionen/);
  assert.match(workspaceEditorSource, /title="Als Vorlage speichern"[\s\S]*?@click="saveCurrentNoteAsTemplate"/);
  assert.match(workspaceEditorSource, /title="Versionsverlauf"[\s\S]*?@click="openVersionHistory"/);
  assert.match(workspaceEditorSource, /title="Tastenkürzel"[\s\S]*?@click="openNoteShortcuts"/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__more-group-label">Exportieren/);
  assert.match(workspaceEditorSource, /title="Markdown"[\s\S]*?@click="exportNoteAsMarkdown"/);
  assert.match(workspaceEditorSource, /title="PDF"[\s\S]*?@click="exportNoteAsPdf"/);
  assert.equal((workspaceEditorSource.match(/class="note-workspace-editor__more-item"/g) || []).length, 5);
  assert.equal((workspaceEditorSource.match(/class="note-workspace-editor__more-icon"/g) || []).length, 5);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-menu\s*\{[\s\S]*?padding:\s*6px[\s\S]*?border-radius:\s*14px[\s\S]*?background:\s*var\(--pm-app-surface-raised\)[\s\S]*?box-shadow:\s*var\(--pm-shadow\)/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-item\s*\{[\s\S]*?min-height:\s*38px[\s\S]*?border-radius:\s*9px[\s\S]*?transition:\s*none/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-icon\s*\{[\s\S]*?width:\s*26px[\s\S]*?height:\s*26px[\s\S]*?border-radius:\s*8px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-item:hover,[\s\S]*?background:\s*color-mix\(in srgb, var\(--pm-accent\) 6%, transparent\)/);
  assert.doesNotMatch(workspaceEditorSource, /\.note-workspace-editor__more-item:hover[^{]*\{[^}]*transform:/);
  assert.match(workspaceEditorSource, /moreMenuProps[\s\S]*?note-workspace-editor__more-btn[\s\S]*?mdi-dots-vertical/);
  assert.match(workspaceEditorSource, /v-model="templateTitleDialogOpen"[\s\S]*?title="Vorlage benennen"[\s\S]*?:primary-disabled="!templateTitleInput\.trim\(\)"/);
  assert.match(workspaceEditorSource, /v-model="templateTitleInput"[\s\S]*?label="Titel der Vorlage"[\s\S]*?@keydown\.enter\.prevent="confirmTemplateTitle"/);
  assert.match(workspaceEditorSource, /async function saveCurrentNoteAsTemplate\(\)[\s\S]*?if \(!currentTitle\)[\s\S]*?templateTitleDialogOpen\.value = true/);
  assert.match(workspaceEditorSource, /saveAsTemplate\(noteId, \{ title: templateTitle \}\)[\s\S]*?title: 'Vorlage gespeichert'[\s\S]*?critical: true/);
  assert.match(workspaceEditorSource, /noteToMarkdown\(\{ title: title\.value, body: body\.value \}\)/);
  assert.match(workspaceEditorSource, /noteToPrintableHtml\(\{/);
});

test('template boxes use a compact accessible save icon button', () => {
  assert.match(templateBoxViewSource, /class="pm-template__save"[\s\S]*?aria-label="Als Schnellblock speichern"[\s\S]*?<v-icon size="16">mdi-content-save-outline<\/v-icon>/);
  assert.doesNotMatch(templateBoxViewSource, />Als Baustein speichern<\/button>/);
  assert.match(templateBoxViewSource, /\.pm-template__save\s*{[\s\S]*?width:\s*28px;[\s\S]*?height:\s*28px;[\s\S]*?place-items:\s*center/);
});

test('note history lists bundled checkpoints and restores a selected server revision', () => {
  assert.match(workspaceEditorSource, /<NoteVersionHistoryDialog[\s\S]*?v-model="historyOpen"/);
  assert.match(workspaceEditorSource, /history_reason: snapshot\.historyReason \|\| 'autosave'/);
  assert.match(workspaceEditorSource, /checkpointNoteRevision\(noteId, reason\)/);
  assert.match(workspaceEditorSource, /notesStore\.restoreRevision\(noteId, revision\.id, serverRevision\.value\)/);
  assert.match(notesApiSource, /listNoteRevisions[\s\S]*?\/revisions\?limit=/);
  assert.match(notesApiSource, /restoreNoteRevision[\s\S]*?\/restore/);
  assert.match(noteVersionHistorySource, /title="Versionsverlauf"/);
  assert.match(noteVersionHistorySource, /Diesen Stand wiederherstellen/);
  assert.match(noteVersionHistorySource, /Autosaves werden gebündelt/);
  assert.match(noteVersionHistorySource, /KI-Übernahme/);
  assert.match(noteVersionHistorySource, /Vor Wiederherstellung/);
  assert.match(noteVersionHistorySource, /revision\.note_revision === currentRevision/);
});

test('workspace utility buttons share one quiet visual treatment', () => {
  assert.match(workspaceEditorSource, /\.note-workspace-editor__actions\s*\{[\s\S]*?gap:\s*4px/);
  assert.equal((workspaceEditorSource.match(/'pm-header-icon-btn--quiet'/g) || []).length, 3);
  assert.equal((workspaceEditorSource.match(/<PmActionIcon/g) || []).length, 1);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__more-btn"[\s\S]*?variant="text"/);
  assert.match(workspaceEditorSource, /<PmActionIcon :name="listVisible \? 'fullscreen' : 'fullscreen-exit'" \/>/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-btn\s*\{[\s\S]*?margin-right:\s*-8px/);
  assert.doesNotMatch(workspaceEditorSource, /\.note-workspace-editor__view-divider\s*\{/);
  assert.match(workspaceEditorSource, /:variant="listVisible \? 'text' : 'tonal'"/);
});

test('workspace tags sit in the compact metadata row instead of a separate editor bar', () => {
  assert.doesNotMatch(workspaceEditorSource, /class="note-workspace-editor__tags"/);
  assert.doesNotMatch(workspaceEditorSource, /\.note-workspace-editor__tags\s*\{/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__meta"[\s\S]*?class="note-workspace-editor__meta-tags"[\s\S]*?<NoteTagBar[\s\S]*?compact/);
  assert.match(workspaceEditorSource, /:tag-ids="noteTagIds"[\s\S]*?:load-tags="tagStore\.fetchTags"/);
  assert.match(workspaceEditorSource, /@update:tag-ids="applyNoteTagIds"/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__actions\s*\{[\s\S]*?flex:\s*0 0 auto;/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags\s*\{[\s\S]*?overflow:\s*hidden/);
});

test('linked document thumbnails have a subtle theme-aware frame', () => {
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__document-popover-summary img\s*\{[\s\S]*?border:\s*1px solid rgba\(var\(--v-theme-on-surface\), 0\.16\)/,
  );
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__picker-row img\s*\{[\s\S]*?border:\s*1px solid rgba\(var\(--v-theme-on-surface\), 0\.18\)/,
  );
});

test('workspace title is prominent while keeping the compact left inset', () => {
  assert.match(workspaceEditorSource, /\.note-workspace-editor__bar\s*\{[\s\S]*?align-items:\s*center;[\s\S]*?padding:\s*7px 16px 7px 7px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__title\s*\{[\s\S]*?font-size:\s*1\.125rem;[\s\S]*?padding:\s*8px 9px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta\s*\{[\s\S]*?padding:\s*0 16px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input\)\s*\{[\s\S]*?gap:\s*0/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input__chips:not\(:empty\)\)\s*\{[\s\S]*?margin-right:\s*7px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-main,\s*\n\.note-workspace-editor__sync,\s*\n\.note-workspace-editor__word-count\s*\{[\s\S]*?top:\s*-4px/);
});

test('fullscreen metadata row grows to the same width as the title row', () => {
  assert.match(workspaceEditorSource, /v-if="hasLoadedContent" class="note-workspace-editor__meta"/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__meta"\s*:class="\{ 'is-centered': !listVisible \}"/);
  assert.doesNotMatch(workspaceEditorSource, /\.note-workspace-editor__meta\.is-centered/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta\s*\{[\s\S]*?display:\s*flex;[\s\S]*?padding:\s*0 16px/);
});

test('list and editor headers share one separator height', () => {
  assert.match(workspaceSource, /--notes-header-height:\s*54px/);
  assert.match(workspaceSource, /--notes-meta-row-height:\s*36px/);
  assert.match(workspaceSource, /\.notes-ws__header\s*\{[\s\S]*?box-sizing:\s*border-box;[\s\S]*?height:\s*var\(--notes-header-height\);[\s\S]*?min-height:\s*var\(--notes-header-height\)/);
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__bar\s*\{[\s\S]*?box-sizing:\s*border-box;[\s\S]*?height:\s*var\(--notes-header-height, 54px\);[\s\S]*?min-height:\s*var\(--notes-header-height, 54px\)/,
  );
  assert.match(listActionToolbarSource, /box-sizing:\s*border-box;[\s\S]*?height:\s*var\(--notes-meta-row-height, 36px\)/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta\s*\{[\s\S]*?box-sizing:\s*border-box;[\s\S]*?height:\s*var\(--notes-meta-row-height, 36px\)/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-main\s*\{[\s\S]*?flex-wrap:\s*nowrap/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input\)\s*\{[\s\S]*?flex-wrap:\s*nowrap/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-tags :deep\(\.pm-tags-input__chips\)\s*\{[\s\S]*?flex-wrap:\s*nowrap;[\s\S]*?overflow-x:\s*auto/);
});

test('editor metadata actions use exactly the same surface as the title row', () => {
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor\s*\{[\s\S]*?--pm-note-editor-header-bg:\s*rgba\(var\(--v-theme-surface\), 0\.68\)/,
  );
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__bar\s*\{[\s\S]*?background:\s*var\(--pm-note-editor-header-bg\)/,
  );
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__meta\s*\{[\s\S]*?background:\s*var\(--pm-note-editor-header-bg\)/,
  );
});

test('workspace editor omits the last-edited metadata area completely', () => {
  assert.doesNotMatch(workspaceEditorSource, /Zuletzt|lastEdited|formatRelativeDate/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__meta-(line|divider|chip)/);
  assert.doesNotMatch(templateSource, /:updated-at="activeNote\.updated_at"/);
});

test('embedded note editor has a persistent formatting toolbar', () => {
  assert.match(noteEditorSource, /note-editor__toolbar/);
  assert.match(noteEditorSource, /key: 'h2', label: 'Überschrift 2'/);
  assert.match(noteEditorSource, /key: 'h4', label: 'Überschrift 4'/);
  assert.match(noteEditorSource, /bold: \(\) => chain\.toggleBold\(\)/);
  assert.match(noteEditorSource, /key: 'bulletList',[^\n]+label: 'Aufzählung'/);
  assert.match(noteEditorSource, /\.note-editor--workspace \.note-editor__surface\s*\{[\s\S]*?padding:\s*24px clamp\(28px, 5vw, 58px\) 88px/);
});

test('empty workspace notes use a calm two-level writing invitation', () => {
  assert.match(noteEditorSource, /placeholder:\s*\{ type: String, default: 'Einfach losschreiben …' \}/);
  assert.match(noteEditorSource, /v-if="workspace && editorEmpty"[\s\S]*?class="note-editor__empty-hint"/);
  assert.match(noteEditorSource, /<kbd>\/<\/kbd>[\s\S]*?für Überschriften, Listen und weitere Blöcke/);
  assert.match(noteEditorSource, /function isPristineEmptyDocument\(ed\)/);
  assert.match(noteEditorSource, /doc\?\.childCount === 1[\s\S]*?firstBlock\?\.type\?\.name === 'paragraph'[\s\S]*?firstBlock\.content\.size === 0/);
  assert.match(noteEditorSource, /editorEmpty\.value = isPristineEmptyDocument\(ed\)/);
  assert.doesNotMatch(noteEditorSource, /editorEmpty\.value = Boolean\(ed\?\.isEmpty\)/);
  assert.match(noteEditorSource, /const firstParagraph = writing\?\.querySelector\('\.pm-content > p:first-child'\)/);
  assert.match(noteEditorSource, /top: `\$\{paragraphRect\.top - writingRect\.top\}px`/);
  assert.match(noteEditorSource, /\.note-editor__empty-hint\.is-positioned\s*\{[\s\S]*?note-editor-empty-hint-in/);
  assert.match(noteEditorSource, /\.note-editor__empty-hint-detail kbd\s*\{[\s\S]*?border-radius:\s*6px/);
  assert.match(noteEditorSource, /\.note-editor--workspace :deep\(\.pm-content p\.is-editor-empty:first-child::before\)\s*\{[\s\S]*?content:\s*none/);
});

test('word count is metadata in the header instead of a formatting control', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__meta"[\s\S]*?class="note-workspace-editor__word-count"[\s\S]*?wordCount === 1 \? 'Wort' : 'Wörter'/);
  assert.match(workspaceEditorSource, /@word-count="updateWordCount"/);
  assert.match(noteEditorSource, /emit\('word-count', words\.value\)/);
  assert.doesNotMatch(noteEditorSource, /note-editor__toolbar-count/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__footer/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__word-count\s*\{[\s\S]*?align-self:\s*center;[\s\S]*?margin-left:\s*auto;[\s\S]*?font-variant-numeric:\s*tabular-nums/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__meta-main\s*\{[\s\S]*?flex:\s*1 1 auto;[\s\S]*?flex-wrap:\s*nowrap/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__more-btn\s*\{[\s\S]*?margin-right:\s*-8px/);
});

test('first heading starts at the same content inset as body text', () => {
  assert.match(
    noteEditorSource,
    /\.pm-content > :is\(h1, h2, h3, h4, h5, h6\):first-child\)[\s\S]*?margin-top:\s*0/,
  );
});

test('workspace formatting controls render as a flat inset sticky palette', () => {
  const toolbarStyle = noteEditorSource.match(/\.note-editor__toolbar\s*\{([\s\S]*?)\n\}/)?.[1] || '';
  // Der Guard liefert die deckende, sticky Fläche hinter der Leiste.
  assert.match(noteEditorSource, /class="note-editor__toolbar-guard"[\s\S]*?class="note-editor__toolbar"/);
  assert.match(noteEditorSource, /\.note-editor__toolbar-guard\s*\{[\s\S]*?position:\s*sticky;[\s\S]*?top:\s*0;[\s\S]*?width:\s*100%;[\s\S]*?background:\s*var\(--pm-content-surface, #fff\)/);
  assert.match(noteEditorSource, /\.note-editor__toolbar-guard::after\s*\{[\s\S]*?top:\s*100%;[\s\S]*?height:\s*20px;[\s\S]*?pointer-events:\s*none;[\s\S]*?linear-gradient/);
  // Die Leiste selbst: volle Breite, linksbündig, flach (kein eigener Hintergrund).
  assert.match(toolbarStyle, /position:\s*relative/);
  assert.match(toolbarStyle, /width:\s*calc\(100% - 16px\)/);
  assert.match(toolbarStyle, /align-self:\s*flex-start/);
  assert.match(toolbarStyle, /margin:\s*8px 0 0 8px/);
  assert.match(toolbarStyle, /padding:\s*5px 7px 5px 0/);
  assert.match(toolbarStyle, /border-radius:\s*12px/);
  assert.match(toolbarStyle, /background:\s*transparent/);
  assert.match(toolbarStyle, /box-shadow:\s*none/);
  assert.doesNotMatch(toolbarStyle, /border-(top|bottom):/);
});

test('workspace editor uses the full width with equal small gutters in fullscreen mode', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__body"/);
  assert.match(workspaceEditorSource, /'is-fullscreen': !listVisible/);
  assert.doesNotMatch(workspaceEditorSource, /'is-centered': !listVisible/);
  assert.match(noteEditorSource, /\.note-editor--workspace\.is-fullscreen \.note-editor__surface\s*{[\s\S]*?padding-inline:\s*28px/);
  assert.match(noteEditorSource, /\.note-editor--workspace\.is-fullscreen \.note-editor__writing\s*{[\s\S]*?max-width:\s*none;[\s\S]*?margin-inline:\s*0/);
  assert.match(noteEditorSource, /\.note-editor--workspace\.is-fullscreen\s+:deep\(\.pm-content\)\s*{[\s\S]*?width:\s*100%;[\s\S]*?max-width:\s*none/);
});

test('formatting palette stays flat with no background or scroll-duck', () => {
  const toolbarStyle = noteEditorSource.match(/\.note-editor__toolbar\s*\{([\s\S]*?)\n\}/)?.[1] || '';
  // Immer flach: kein Hintergrund, kein Schatten – auch nicht bei offenem Menü.
  assert.match(toolbarStyle, /background:\s*transparent/);
  assert.match(toolbarStyle, /box-shadow:\s*none/);
  // Die frühere Scroll-Duck-Mechanik ist vollständig entfernt.
  assert.doesNotMatch(noteEditorSource, /is-ducked/);
  assert.doesNotMatch(noteEditorSource, /toolbarDucked/);
  assert.doesNotMatch(noteEditorSource, /TOOLBAR_DUCK_SCROLL_THRESHOLD/);
});

test('selection formatting stays above the notes list instead of being clipped by the editor scroller', () => {
  assert.match(noteEditorSource, /ref="bubbleEl"[\s\S]*?class="pm-float pm-bubble"/);
  assert.match(noteEditorSource, /const bubbleEl = ref\(null\)/);
  assert.match(noteEditorSource, /import \{ TextSelection \} from '@tiptap\/pm\/state'/);
  assert.match(noteEditorSource, /state\.selection instanceof TextSelection/);
  assert.doesNotMatch(noteEditorSource, /selection\.constructor\?\.name === 'TextSelection'/);
  assert.doesNotMatch(noteEditorSource, /hasOwnProperty\.call\(state\.selection, '\$cursor'\)/);
  assert.match(noteEditorSource, /rect\.left \+ rect\.width \/ 2/);
  assert.match(noteEditorSource, /bubbleEl\.value\?\.offsetWidth/);
  assert.match(noteEditorSource, /bubbleEl\.value\?\.offsetHeight/);
  assert.match(noteEditorSource, /querySelector\('\.note-editor__toolbar-guard'\)/);
  assert.match(noteEditorSource, /toolbarRect\?\.bottom/);
  assert.match(noteEditorSource, /placeSelectionBubble/);
  assert.match(noteEditorSource, /transform: 'translateX\(-50%\)'/);
  assert.match(noteEditorSource, /window\.innerWidth - BUBBLE_VIEWPORT_MARGIN/);
  assert.match(noteEditorSource, /if \(bubble\.show\) refreshBubble\(\)/);
  assert.match(noteEditorSource, /window\.addEventListener\('resize', refreshBubble\)/);
  assert.match(noteEditorSource, /window\.removeEventListener\('resize', refreshBubble\)/);
  assert.match(noteEditorSource, /\.pm-bubble\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?z-index:\s*80;[\s\S]*?max-width:\s*calc\(100vw - 16px\)/);
});

test('slash menu stays in the visible editor viewport without moving the writing position', () => {
  assert.match(noteEditorSource, /ref="surfaceEl"[\s\S]*?class="note-editor__surface"/);
  assert.match(noteEditorSource, /toolbarScrollContainer\?\.getBoundingClientRect\(\)/);
  assert.match(noteEditorSource, /Math\.min\(window\.innerHeight, scrollRect\?\.bottom/);
  assert.match(noteEditorSource, /spaceBelow < MENU_MIN_OPEN_HEIGHT && spaceAbove > spaceBelow/);
  assert.match(noteEditorSource, /maxHeight: `\$\{Math\.floor\(maxHeight\)\}px`/);
  assert.match(noteEditorSource, /const scrollTopBeforeOpen = opening && toolbarScrollContainer/);
  assert.match(noteEditorSource, /nextTick\(\(\) => restoreWorkspaceScroll\(scrollTopBeforeOpen\)\)/);
  assert.match(noteEditorSource, /\.pm-slash--commands\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?overflow-anchor:\s*none;/);
});

test('picker menus remain anchored to the editor surface with a compact gap', () => {
  assert.match(noteEditorSource, /function positionPicker\(\)[\s\S]*?const box = surface\.getBoundingClientRect\(\)/);
  assert.match(noteEditorSource, /rect\.bottom - box\.top \+ 4/);
  assert.doesNotMatch(noteEditorSource, /root\.getBoundingClientRect\(\)/);
});

test('the compact notes list offers a notebook filter in its toolbar', () => {
  // Eigener State + reiner Client-Filter über note.notebook_id.
  assert.match(workspaceSource, /const notebookFilter = ref\(''\)/);
  assert.match(
    workspaceSource,
    /function matchesNotebookFilter\(note\)[\s\S]*?notebookFilter\.value === 'none'[\s\S]*?return !note\.notebook_id[\s\S]*?return note\.notebook_id === notebookFilter\.value/,
  );
  assert.match(workspaceSource, /\.filter\(matchesNotebookFilter\)/);
  // Als datengetriebene Toolbar-Aktion, nur wenn es Notizbücher gibt.
  assert.match(workspaceSource, /if \(notesStore\.notebooks\.length\)[\s\S]*?key: 'notebook'/);
  assert.match(workspaceSource, /if \(action === 'notebook'\) notebookFilter\.value = value/);
  assert.match(workspaceSource, /notesStore\.ensureNotebooksLoaded\(\)/);
});

test('creating a note inside a filtered notebook keeps it in that notebook', () => {
  assert.match(
    workspaceSource,
    /function newNoteInitial\(\)[\s\S]*?notebookFilter\.value !== 'none'[\s\S]*?\{ notebook_id: notebookFilter\.value \}/,
  );
  assert.match(workspaceSource, /notesStore\.create\(newNoteInitial\(\)\)/);
});

test('compact list filters collapse to icons when inactive so the toolbar never overflows', () => {
  // Inaktive Filter (Standardwert) zeigen nur ihr Icon; aktiv zeigen sie den Wert.
  assert.match(workspaceSource, /iconOnly: !notebookFilter\.value/);
  assert.match(workspaceSource, /iconOnly: !dateRange\.value/);
  // Der Toolbar-Baustein unterstützt iconOnly + kürzt lange Labels per Ellipsis.
  assert.match(listActionToolbarSource, /list-action-toolbar__action-btn--icon-only/);
  assert.match(listActionToolbarSource, /class="list-action-toolbar__action-label"/);
  assert.match(listActionToolbarSource, /\.list-action-toolbar__action-label\s*\{[\s\S]*?text-overflow:\s*ellipsis/);
});

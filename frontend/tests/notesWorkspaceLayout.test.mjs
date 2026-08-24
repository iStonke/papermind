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
const workspaceEditorSource = await readFile(
  new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url),
  'utf8',
);
const noteEditorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
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
const notesApiSource = await readFile(
  new URL('../src/api/notes.js', import.meta.url),
  'utf8',
);
const notesStoreSource = await readFile(
  new URL('../src/stores/notes.js', import.meta.url),
  'utf8',
);
const templateSource = workspaceSource.match(/<template>([\s\S]*?)<\/template>/)?.[1] || '';

test('notes workspace reserves a compact list and a separate editor area', () => {
  assert.match(templateSource, /notes-ws__list-panel/);
  assert.match(templateSource, /notes-ws__editor-slot/);
  assert.match(templateSource, /<NoteWorkspaceEditor/);
  assert.match(workspaceSource, /--notes-list-width:\s*clamp\(300px, 31vw, 380px\)/);
  assert.match(workspaceSource, /\.notes-ws\s*\{[\s\S]*?display:\s*flex/);
});

test('notes list slides in and out while the editor keeps the toggle accessible', () => {
  assert.match(templateSource, /'is-list-collapsed': isListPanelCollapsed/);
  assert.match(templateSource, /:inert="isListPanelCollapsed"/);
  assert.match(templateSource, /@toggle-list="toggleNotesList"/);
  assert.match(templateSource, /<NoteWorkspaceEditor[\s\S]*?v-if="activeNote"/);
  assert.match(templateSource, /v-if="!activeNote && isListPanelCollapsed"[\s\S]*?mdi-arrow-collapse/);
  assert.match(templateSource, /<PmEmptyState[\s\S]*?v-if="!activeNote"[\s\S]*?Keine Notiz ausgewählt/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__list-toggle"/);
  assert.match(workspaceEditorSource, /listVisible \? 'mdi-arrow-expand' : 'mdi-arrow-collapse'/);
  assert.match(workspaceEditorSource, /listVisible \? 'Editor im Vollbild anzeigen' : 'Vollbildansicht verlassen'/);
  assert.match(workspaceEditorSource, /<v-menu[\s\S]*?<\/v-menu>[\s\S]*?class="note-workspace-editor__list-toggle"/);
  assert.match(workspaceEditorSource, /emit\('toggle-list'\)/);
  assert.match(workspaceSource, /margin-left:\s*calc\(-1 \* var\(--notes-list-width\)\)/);
  assert.match(workspaceSource, /transform:\s*translateX\(-18px\)/);
  assert.match(workspaceSource, /localStorage\.setItem\('pm-notes-list-collapsed'/);
  assert.match(workspaceSource, /prefers-reduced-motion:\s*reduce[\s\S]*notes-ws__list-panel/);
  assert.match(workspaceSource, /pm-no-animations[\s\S]*notes-ws__list-panel/);
});

test('notes list follows the shared title, toolbar, and row hierarchy', () => {
  assert.match(templateSource, />\s*Notizen\s*</);
  assert.match(templateSource, /Neue Notiz/);
  assert.match(templateSource, /<ListActionToolbar/);
  assert.match(templateSource, /:actions="toolbarActions"/);
  assert.match(templateSource, /:show-selection="false"/);
  assert.match(templateSource, /notes-ws__item-snippet/);
  assert.match(workspaceSource, /notes-ws__item\.is-active/);
  assert.doesNotMatch(templateSource, /<v-text-field|type="search"|notes-ws__toggle/);
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

test('empty editor reuses the static document-preview placeholder pattern', () => {
  assert.match(templateSource, /title="[^"]*Keine Notiz ausgewählt[^"]*"/);
  assert.match(templateSource, /subtitle="[^"]*Wähle eine Notiz aus der Liste, um den Editor zu öffnen\.[^"]*"/);
  assert.match(templateSource, /size="md"[\s\S]*?:animated="false"/);
  assert.doesNotMatch(workspaceSource, /notes-ws__editor-(canvas|placeholder|icon)/);
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
  assert.match(noteEditorSource, /note-editor--spacing-compact[\s\S]*?--note-editor-paragraph-gap:\s*0\.45em/);
  assert.match(noteEditorSource, /note-editor--spacing-spacious[\s\S]*?--note-editor-paragraph-gap:\s*1\.05em/);
  assert.match(noteEditorSource, /note-editor--font-serif[\s\S]*?--note-editor-font-family:\s*Georgia/);
  assert.match(noteEditorSource, /note-editor--font-mono[\s\S]*?--note-editor-font-family:\s*ui-monospace/);
  assert.match(noteEditorSource, /\.pm-content h[12]\)[\s\S]*?font-family:\s*inherit/);
  assert.match(noteEditorSource, /setAttribute\('spellcheck', enabled \? 'true' : 'false'\)/);
});

test('new-note action exists only inside the notes workspace', () => {
  assert.match(templateSource, /Neue Notiz/);
  assert.match(templateSource, /class="list-header-btn"[\s\S]*?color="primary"[\s\S]*?variant="tonal"/);
  assert.match(templateSource, /<v-icon size="18" class="mr-1">mdi-plus<\/v-icon>/);
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

test('removing a note reuses the document collapse timing before updating the list', () => {
  assert.match(workspaceSource, /NOTE_REMOVAL_DURATION_MS\s*=\s*210/);
  assert.match(workspaceSource, /notesStore\.trash\(note\.id\)[\s\S]*animateNoteRemoval\(note\.id\)[\s\S]*notesStore\.removeFromList\(note\.id\)/);
  assert.match(workspaceSource, /height 210ms[\s\S]*opacity 160ms[\s\S]*transform 180ms/);
  assert.match(documentListPanelSource, /height 210ms[\s\S]*opacity 160ms[\s\S]*transform 180ms/);
  assert.match(workspaceSource, /pm-no-animations[\s\S]*notes-ws__item\.is-removing/);
});

test('empty notes are permanently removed instead of entering the trash', () => {
  assert.match(workspaceSource, /noteIsEmptyForDeletion\(note\)[\s\S]*discardEmptyNote\(note\)/);
  assert.match(
    workspaceSource,
    /notesStore\.deletePermanently\(note\.id\)[\s\S]*animateNoteRemoval\(note\.id\)[\s\S]*notesStore\.removeFromList\(note\.id\)/,
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
  assert.match(documentListPanelSource, /aria-label="Gelöschte Notizen"/);
  assert.match(documentListPanelSource, /emit\('restore-note', note\)/);
  assert.match(documentsWorkspaceSource, /:trash-notes="visibleTrashedNotes"/);
  assert.match(documentsWorkspaceSource, /emptyNotesTrash\(\)/);
});

test('workspace editor edits the title in its action bar without a save status', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__title"/);
  assert.match(workspaceEditorSource, /v-model="title"/);
  assert.match(workspaceEditorSource, /@keydown\.enter\.prevent="focusEditorBody"/);
  assert.match(workspaceEditorSource, /Dokument zuordnen/);
  assert.match(workspaceEditorSource, /v-else[\s\S]*?class="note-workspace-editor__document-btn"[\s\S]*?icon="mdi-link-variant"/);
  assert.doesNotMatch(workspaceEditorSource, /saveLabel|note-workspace-editor__save/);
  assert.doesNotMatch(workspaceEditorSource, /v-model:title="title"/);
  assert.match(noteEditorSource, /v-if="!workspace"[\s\S]*?class="note-editor__title"/);
  assert.doesNotMatch(noteEditorSource, /note-editor--workspace \.note-editor__title/);
  assert.doesNotMatch(workspaceEditorSource, /mdi-star-outline/);
  assert.doesNotMatch(workspaceEditorSource, /toggleFavorite/);
  assert.doesNotMatch(workspaceEditorSource, />Löschen<\/button>/);
  assert.doesNotMatch(templateSource, /@delete="removeNote\(activeNote\)"/);
  assert.match(workspaceEditorSource, /notesStore\.update/);
  assert.match(workspaceEditorSource, /setTimeout\([\s\S]*650/);
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
  assert.match(notesStoreSource, /const optimisticDetail = previousDetail \? \{ \.\.\.previousDetail, \.\.\.patch \} : null/);
});

test('editor scroll position is restored per note across switches and reloads', () => {
  assert.match(workspaceEditorSource, /ref="scrollContainerRef"[\s\S]*?@scroll\.passive="rememberScrollPosition\(\)"/);
  assert.match(workspaceEditorSource, /NOTE_SCROLL_POSITIONS_STORAGE_KEY\s*=\s*'pm-note-scroll-positions-v1'/);
  assert.match(workspaceEditorSource, /NOTE_SCROLL_POSITIONS_LIMIT\s*=\s*100/);
  assert.match(workspaceEditorSource, /rememberScrollPosition\(loadedNoteId\.value\)[\s\S]*?flushSave\(\)/);
  assert.match(workspaceEditorSource, /restoreScrollPosition\(noteId\)/);
  assert.match(workspaceEditorSource, /window\.localStorage\.setItem\([\s\S]*?NOTE_SCROLL_POSITIONS_STORAGE_KEY/);
  assert.match(noteEditorSource, /function restoreWorkspaceScroll\(top\)/);
  assert.match(noteEditorSource, /defineExpose\(\{ focusTitle, focusBody, restoreWorkspaceScroll \}\)/);
  assert.match(noteEditorSource, /if \(restoringWorkspaceScroll\)[\s\S]*?toolbarScrollAnchor = scrollTop/);
});

test('the complete editor whitespace focuses the caret at the end of the note', () => {
  assert.match(noteEditorSource, /@pointerdown="focusEditorEndFromWhitespace"/);
  assert.match(noteEditorSource, /function focusEditorEndFromWhitespace\(event\)/);
  assert.match(noteEditorSource, /target\.closest\('\.pm-float, button, input, select, textarea, a'\)/);
  assert.match(noteEditorSource, /content\.contains\(target\) && target !== content/);
  assert.match(noteEditorSource, /ed\.chain\(\)\.focus\('end'\)\.run\(\)/);
  assert.match(noteEditorSource, /\.note-editor__surface\s*\{[\s\S]*?cursor:\s*text/);
});

test('linked documents use a compact header chip and the library picker pattern', () => {
  assert.match(workspaceEditorSource, /v-if="linkedDocument"[\s\S]*?class="note-workspace-editor__document-chip"/);
  assert.match(workspaceEditorSource, /note-workspace-editor__document-chip-label/);
  assert.match(workspaceEditorSource, /title="Dokument öffnen"[\s\S]*?title="Dokument wechseln"[\s\S]*?title="Verknüpfung lösen"/);
  assert.match(workspaceEditorSource, /<BaseDialog[\s\S]*?title="Dokument zuordnen"[\s\S]*?PaperMind-Bibliothek[\s\S]*?max-width="780"[\s\S]*?scrollable/);
  assert.match(workspaceEditorSource, /placeholder="Dokumente suchen"/);
  assert.match(workspaceEditorSource, /v-for="document in documentPickerDocuments"[\s\S]*?documentThumbnailUrl\(document\.id\)/);
  assert.match(workspaceEditorSource, /documentPickerSearchTimer[\s\S]*?280/);
  assert.match(workspaceEditorSource, /useSettingsStore/);
  assert.match(workspaceEditorSource, /showFilenameSuffix/);
  assert.match(workspaceEditorSource, /formatDocumentFilename[\s\S]*?replace\(\/\\\.\[A-Za-z\]/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__document-chip-label\s*\{[\s\S]*?font-weight:\s*400/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__document-card/);
});

test('document assignment gives the action and resulting chip reduced-motion-safe feedback', () => {
  assert.match(
    workspaceEditorSource,
    /class="note-workspace-editor__document-btn"[\s\S]*?:class="\{ 'is-activating': documentLinkActionActive \}"/,
  );
  assert.match(workspaceEditorSource, /async function openDocumentPicker\(\) \{[\s\S]*?triggerDocumentLinkAction\(\)/);
  assert.match(workspaceEditorSource, /function assignDocument\(document\)[\s\S]*?triggerDocumentChipArrival\(\)/);
  assert.match(workspaceEditorSource, /@keyframes pm-document-action-pulse/);
  assert.match(workspaceEditorSource, /@keyframes pm-document-link-icon/);
  assert.match(workspaceEditorSource, /@keyframes pm-document-chip-arrive/);
  assert.match(workspaceEditorSource, /@keyframes pm-document-chip-sheen/);
  assert.match(
    workspaceEditorSource,
    /prefers-reduced-motion:\s*reduce[\s\S]*?document-btn\.v-btn\.is-activating[\s\S]*?document-chip\.is-arriving/,
  );
  assert.match(workspaceEditorSource, /pm-no-animations[\s\S]*?document-chip\.is-arriving/);
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

test('note export sits between document linking and fullscreen and includes sources', () => {
  const documentAction = workspaceEditorSource.indexOf('class="note-workspace-editor__document-btn"');
  const exportAction = workspaceEditorSource.indexOf('class="note-workspace-editor__export-btn"');
  const fullscreenAction = workspaceEditorSource.indexOf('class="note-workspace-editor__list-toggle"');
  assert.ok(documentAction >= 0 && documentAction < exportAction);
  assert.ok(exportAction < fullscreenAction);
  assert.match(workspaceEditorSource, /icon="mdi-download-outline"/);
  assert.match(workspaceEditorSource, /title="Markdown"[\s\S]*?@click="exportNoteAsMarkdown"/);
  assert.match(workspaceEditorSource, /title="PDF"[\s\S]*?@click="exportNoteAsPdf"/);
  assert.match(workspaceEditorSource, /noteToMarkdown\(\{ title: title\.value, body: body\.value \}\)/);
  assert.match(workspaceEditorSource, /noteToPrintableHtml\(\{/);
});

test('workspace utility buttons share one quiet visual treatment', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__document-btn"[\s\S]*?variant="text"/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__actions\s*\{[\s\S]*?gap:\s*6px/);
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__document-btn\.v-btn,[\s\S]*?\.note-workspace-editor__export-btn\.v-btn,[\s\S]*?\.note-workspace-editor__list-toggle\.v-btn\s*\{[\s\S]*?width:\s*40px;[\s\S]*?height:\s*40px;[\s\S]*?min-width:\s*40px/,
  );
  assert.match(workspaceEditorSource, /\.note-workspace-editor__list-toggle\.v-btn :deep\(\.v-icon\)[\s\S]*?font-size:\s*20px/);
  assert.match(workspaceEditorSource, /:variant="listVisible \? 'text' : 'tonal'"/);
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

test('workspace title uses the same compact left inset as neighboring controls', () => {
  assert.match(workspaceEditorSource, /\.note-workspace-editor__bar\s*\{[\s\S]*?padding:\s*9px 16px 9px 7px/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__title\s*\{[\s\S]*?padding:\s*8px 9px/);
});

test('list and editor headers share one separator height', () => {
  assert.match(workspaceSource, /--notes-header-height:\s*60px/);
  assert.match(workspaceSource, /\.notes-ws__header\s*\{[\s\S]*?min-height:\s*var\(--notes-header-height\)/);
  assert.match(
    workspaceEditorSource,
    /\.note-workspace-editor__bar\s*\{[\s\S]*?min-height:\s*var\(--notes-header-height, 60px\)/,
  );
});

test('workspace editor omits the last-edited metadata area completely', () => {
  assert.doesNotMatch(workspaceEditorSource, /Zuletzt|lastEdited|formatRelativeDate/);
  assert.doesNotMatch(workspaceEditorSource, /note-workspace-editor__meta-(line|divider|chip)/);
  assert.doesNotMatch(templateSource, /:updated-at="activeNote\.updated_at"/);
});

test('embedded note editor has a persistent formatting toolbar', () => {
  assert.match(noteEditorSource, /note-editor__toolbar/);
  assert.match(noteEditorSource, /runToolbar\('h2'\)/);
  assert.match(noteEditorSource, /runToolbar\('h4'\)/);
  assert.match(noteEditorSource, /runToolbar\('bold'\)/);
  assert.match(noteEditorSource, /runToolbar\('bulletList'\)/);
  assert.match(noteEditorSource, /\.note-editor--workspace \.note-editor__surface\s*\{[\s\S]*?padding:\s*24px clamp\(28px, 5vw, 58px\) 88px/);
});

test('word count is metadata in the header instead of a formatting control', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__word-count"[\s\S]*?wordCount === 1 \? 'Wort' : 'Wörter'/);
  assert.match(workspaceEditorSource, /@word-count="updateWordCount"/);
  assert.match(noteEditorSource, /emit\('word-count', words\.value\)/);
  assert.doesNotMatch(noteEditorSource, /note-editor__toolbar-count/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__word-count\s*\{[\s\S]*?font-variant-numeric:\s*tabular-nums/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__actions-divider\s*\{[\s\S]*?height:\s*20px/);
});

test('first heading starts at the same content inset as body text', () => {
  assert.match(
    noteEditorSource,
    /\.pm-content > h2:first-child\)[\s\S]*?\.pm-content > h3:first-child\)[\s\S]*?\.pm-content > h4:first-child\)[\s\S]*?margin-top:\s*0/,
  );
});

test('workspace formatting controls render as an inset sticky palette', () => {
  const toolbarStyle = noteEditorSource.match(/\.note-editor__toolbar\s*\{([\s\S]*?)\n\}/)?.[1] || '';
  assert.match(noteEditorSource, /\.note-editor__toolbar\s*\{[\s\S]*?position:\s*sticky/);
  assert.match(noteEditorSource, /top:\s*12px/);
  assert.match(noteEditorSource, /width:\s*max-content/);
  assert.match(noteEditorSource, /align-self:\s*center/);
  assert.match(noteEditorSource, /margin:\s*12px auto 0/);
  assert.match(noteEditorSource, /border-radius:\s*12px/);
  assert.match(noteEditorSource, /box-shadow:\s*0 8px 24px/);
  assert.doesNotMatch(toolbarStyle, /border-(top|bottom):/);
});

test('workspace editor centers its writing column in fullscreen mode', () => {
  assert.match(workspaceEditorSource, /class="note-workspace-editor__body"/);
  assert.match(workspaceEditorSource, /'is-centered': !listVisible/);
  assert.match(workspaceEditorSource, /\.note-workspace-editor__body\.is-centered\s+:deep\(\.pm-content\)[\s\S]*?width:\s*100%[\s\S]*?margin-inline:\s*auto/);
});

test('formatting palette quiets its chrome without moving or fading its controls', () => {
  const duckedStyle = noteEditorSource.match(/\.note-editor__toolbar\.is-ducked\s*\{([\s\S]*?)\n\}/)?.[1] || '';
  assert.match(noteEditorSource, /'is-ducked': toolbarDucked/);
  assert.match(noteEditorSource, /addEventListener\('scroll', onEditorScroll, \{ passive: true \}\)/);
  assert.match(noteEditorSource, /TOOLBAR_DUCK_SCROLL_THRESHOLD\s*=\s*24/);
  assert.match(noteEditorSource, /TOOLBAR_REVEAL_DELAY_MS\s*=\s*400/);
  assert.match(noteEditorSource, /Math\.abs\(scrollTop - toolbarScrollAnchor\)/);
  assert.match(duckedStyle, /background:\s*color-mix\([^\n]*52%/);
  assert.match(duckedStyle, /border-color:\s*color-mix\([^\n]*18%/);
  assert.match(duckedStyle, /box-shadow:\s*0 1px 4px/);
  assert.doesNotMatch(duckedStyle, /opacity|transform/);
  assert.match(noteEditorSource, /is-ducked:hover[\s\S]*?is-ducked:focus-within/);
  assert.match(noteEditorSource, /prefers-reduced-motion:\s*reduce[\s\S]*?\.note-editor__toolbar\s*\{[\s\S]*?transition:\s*none/);
});

test('slash and picker menus anchor to the editor surface with a compact gap', () => {
  assert.match(noteEditorSource, /ref="surfaceEl"[\s\S]*?class="note-editor__surface"/);
  assert.match(noteEditorSource, /const box = surface\.getBoundingClientRect\(\)/);
  assert.match(noteEditorSource, /rect\.bottom - box\.top \+ 4/);
  assert.doesNotMatch(noteEditorSource, /root\.getBoundingClientRect\(\)/);
});

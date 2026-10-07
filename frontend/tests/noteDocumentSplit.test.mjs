import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

const pdfPreviewSource = await read('../src/components/PdfPreview.vue');
const paneSource = await read('../src/components/notes/NoteDocumentPane.vue');
const workspaceEditorSource = await read('../src/components/notes/NoteWorkspaceEditor.vue');
const noteEditorSource = await read('../src/components/notes/NoteEditor.vue');
const ocrQuoteSource = await read('../src/components/notes/nodes/ocrQuote.js');
const ocrQuoteViewSource = await read('../src/components/notes/nodes/OcrQuoteView.vue');
const colorsSource = await read('../src/components/notes/learnHighlightColors.js');
const overviewSource = await read('../src/components/notes/DocumentLearnHighlightsSection.vue');
const readerSource = await read('../src/components/DocumentReader.vue');
const documentsWorkspaceSource = await read('../src/views/DocumentsWorkspace.vue');

test('PDF preview offers a quote-only selection mode without reader tools', () => {
  assert.match(pdfPreviewSource, /quoteMode:\s*\{ type: Boolean, default: false \}/);
  assert.match(pdfPreviewSource, /v-if="\(annotatable \|\| quoteMode\) && selectionMenu\.visible"/);
  assert.match(pdfPreviewSource, /v-if="quoteMode && !annotatable"[\s\S]*?In Notiz übernehmen/);
  assert.match(pdfPreviewSource, /if \(!props\.annotatable && !props\.quoteMode\) return;/);
});

test('quote hand-off clears the PDF selection before the editor takes focus', () => {
  assert.match(
    pdfPreviewSource,
    /function requestNoteQuoteFromSelection\(\)[\s\S]*?removeAllRanges\(\);[\s\S]*?hideSelectionMenu\(\);\s*emit\('create-note-quote', payload\);/,
  );
});

test('PDF preview can reveal a quoted region with a transient flash', () => {
  assert.match(pdfPreviewSource, /async function revealRegion\(\{ page, rects, smooth = true \} = \{\}\)/);
  // Nach dem Laden ohne Animation springen (sonst verwirft Chrome den Sprung).
  assert.match(paneSource, /revealRegion\?\.\(\{ \.\.\.request, smooth: false \}\)/);
  assert.match(pdfPreviewSource, /defineExpose\(\{[^}]*revealRegion/);
  assert.match(pdfPreviewSource, /:deep\(\.pdf-preview__flash\)[\s\S]*?animation: pdf-preview-flash/);
});

test('split pane shows the linked document in quote mode and remembers the page per note', () => {
  assert.match(paneSource, /<PdfPreview[\s\S]*?quote-mode[\s\S]*?@create-note-quote="onQuote"/);
  // Nur die Lernmarkierungen dieser Notiz – nie die Lesemodus-Annotationen.
  assert.match(paneSource, /:annotations="highlightAnnotations"/);
  assert.doesNotMatch(paneSource, /listAnnotations|api\/annotations/);
  assert.match(paneSource, /PAGE_STORAGE_KEY = 'pm-note-split-pages-v1'/);
  assert.match(paneSource, /defineExpose\(\{ reveal, reloadHighlights: loadHighlights \}\)/);
});

test('note workspace hosts the split with toggle, splitter and compact tabs', () => {
  assert.match(workspaceEditorSource, /<NoteDocumentPane[\s\S]*?@quote="insertQuoteFromDocument"/);
  assert.match(workspaceEditorSource, /class="note-workspace-editor__split-toggle"[\s\S]*?@click="toggleSplit"/);
  assert.match(workspaceEditorSource, /role="separator"[\s\S]*?@pointerdown="startSplitDrag"/);
  assert.match(workspaceEditorSource, /SPLIT_COMPACT_WIDTH = 860/);
  // Tab-Modus blendet per visibility aus, damit Scrollpositionen erhalten bleiben.
  assert.match(workspaceEditorSource, /\.is-tab-hidden \{[\s\S]*?visibility: hidden;/);
  assert.match(workspaceEditorSource, /window\.addEventListener\('pm-note:quote-reveal', onQuoteReveal\)/);
});

test('quotes are inserted after the current block, never replacing it', () => {
  assert.match(noteEditorSource, /function insertDocumentQuote\(attrs\)/);
  assert.match(noteEditorSource, /at = \$to\.after\(\);/);
  assert.match(noteEditorSource, /insertContentAt\(at, content\)/);
  assert.match(ocrQuoteSource, /rects: \{ default: null, rendered: false \}/);
});

test('quote source link prefers the split view before leaving the notes area', () => {
  assert.match(
    ocrQuoteViewSource,
    /new CustomEvent\('pm-note:quote-reveal', \{\s*cancelable: true,[\s\S]*?if \(!window\.dispatchEvent\(reveal\)\) return;[\s\S]*?'pm-note:navigate'/,
  );
});

test('learn highlights have exactly three fixed meanings', () => {
  for (const key of ['important', 'definition', 'unclear']) {
    assert.match(colorsSource, new RegExp(`key: '${key}'`));
  }
  assert.equal((colorsSource.match(/key: '/g) || []).length, 3);
  assert.match(colorsSource, /Object\.freeze/);
});

test('split pane offers the learn colors and persists them per note', () => {
  assert.match(paneSource, /:selection-colors="LEARN_HIGHLIGHT_COLORS"/);
  assert.match(paneSource, /@create-annotation="onCreateHighlight"/);
  assert.match(paneSource, /createNoteLearnHighlight\(props\.noteId/);
  assert.match(paneSource, /listNoteLearnHighlights\(props\.noteId, props\.documentId\)/);
  // Ohne feste Palette bleibt der Zitat-Modus farblos (Lesemodus-Palette nur annotatable).
  assert.match(pdfPreviewSource, /if \(props\.annotatable\) return ANNOT_COLORS;/);
});

test('reader shows learn highlights only as an optional read-only overlay', () => {
  assert.match(readerSource, /showLearnHighlights = ref\(storedToggles\.learn === true\)/);
  assert.match(readerSource, /:overlay-highlights="showLearnHighlights \? learnOverlay : \[\]"/);
  // Die Overlay-Ebene ist nicht klick-/radierbar und nicht Teil der Annotationen.
  assert.match(pdfPreviewSource, /:deep\(\.pm-overlay-layer\) \{[\s\S]*?pointer-events: none;/);
  assert.doesNotMatch(pdfPreviewSource, /pm-overlay-rect[^\n]*annotId/);
});

test('document overview lists all learn highlights and opens the owning note', () => {
  assert.match(overviewSource, /listDocumentLearnHighlights\(props\.documentId\)/);
  assert.match(overviewSource, /emit\('open-highlight', highlight\)/);
  assert.match(
    documentsWorkspaceSource,
    /function openLearnHighlightInNote\(highlight\)[\s\S]*?requestDocumentReveal\(highlight\.note_id/,
  );
  assert.match(workspaceEditorSource, /notesStore\.consumeDocumentReveal\(noteId\)/);
});

const learnMarkerSource = await read('../src/components/notes/extensions/learnMarker.js');

test('document quotes can carry learn markers like text lines', () => {
  assert.match(learnMarkerSource, /const MARKABLE_TYPES = \[[\s\S]*?'ocrQuote',[\s\S]*?\];/);
  // Atomare Blöcke sind nur per Block-Auswahl bzw. Position greifbar.
  assert.match(learnMarkerSource, /selection instanceof NodeSelection && MARKABLE_TYPES\.includes/);
  assert.match(learnMarkerSource, /toggleLearnMarkerAt:/);
  assert.match(ocrQuoteViewSource, /toggleLearnMarkerAt\(props\.getPos\(\), learnKind\.value \|\| 'lernen'\)/);
  assert.match(ocrQuoteViewSource, /decoration\?\.type\?\.attrs\?\.\['data-learn-state'\]/);
});

test('learn highlight meanings map to learn markers; unclear quotes itself', () => {
  assert.match(colorsSource, /key: 'important'[^\n]*markerKind: 'lernen'/);
  assert.match(colorsSource, /key: 'definition'[^\n]*markerKind: 'fakt'/);
  assert.match(colorsSource, /key: 'unclear'[^\n]*markerKind: 'warum', autoQuote: true/);
  assert.match(paneSource, /learnKind: meaning\?\.markerKind \|\| null/);
  assert.match(paneSource, /autoQuote\(created\);/);
  assert.match(workspaceEditorSource, /if \(auto && hasDocumentQuote\(document\.id, page, text\)\) return;/);
  assert.match(workspaceEditorSource, /learnKind \? \{ learn: learnKind, pmId: randomPmId\(\) \} : \{\}/);
});

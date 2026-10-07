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
  assert.match(pdfPreviewSource, /async function revealRegion\(\{ page, rects \} = \{\}\)/);
  assert.match(pdfPreviewSource, /defineExpose\(\{[^}]*revealRegion/);
  assert.match(pdfPreviewSource, /:deep\(\.pdf-preview__flash\)[\s\S]*?animation: pdf-preview-flash/);
});

test('split pane shows the linked document in quote mode and remembers the page per note', () => {
  assert.match(paneSource, /<PdfPreview[\s\S]*?quote-mode[\s\S]*?@create-note-quote="onQuote"/);
  assert.doesNotMatch(paneSource, /:annotations=/);
  assert.match(paneSource, /PAGE_STORAGE_KEY = 'pm-note-split-pages-v1'/);
  assert.match(paneSource, /defineExpose\(\{ reveal \}\)/);
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

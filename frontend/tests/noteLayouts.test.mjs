import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

import { PaperMindDocument } from '../src/components/notes/nodes/noteDocument.js';
import { LayoutColumn, PageLayout } from '../src/components/notes/nodes/pageLayout.js';
import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';
import {
  NOTE_PAGE_LAYOUT_COLUMNS,
  createNotePageLayout,
  flattenNotePageLayout,
  notePageLayoutColumnCount,
  normalizeNotePageLayoutColumns,
  resizeNotePageLayout,
} from '../src/utils/noteLayouts.js';

const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const previewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const documentSource = await readFile(
  new URL('../src/components/notes/nodes/noteDocument.js', import.meta.url),
  'utf8',
);
const layoutNodeSource = await readFile(
  new URL('../src/components/notes/nodes/pageLayout.js', import.meta.url),
  'utf8',
);

const paragraph = (text) => ({
  type: 'paragraph',
  ...(text ? { content: [{ type: 'text', text }] } : {}),
});

function editorWith(content) {
  return new Editor({
    extensions: [
      StarterKit.configure({ document: false }),
      PageLayout,
      LayoutColumn,
      PaperMindDocument,
    ],
    content: { type: 'doc', content },
  });
}

test('layout menu inserts one through five columns and exposes contextual block actions', () => {
  assert.deepEqual(NOTE_PAGE_LAYOUT_COLUMNS, [1, 2, 3, 4, 5]);
  assert.equal(normalizeNotePageLayoutColumns(8), 5);
  assert.equal(normalizeNotePageLayoutColumns(1), 1);
  assert.equal(normalizeNotePageLayoutColumns(0), 1);
  assert.match(editorSource, /aria-label="Layout"/);
  assert.match(editorSource, /v-for="item in pageLayoutItems"/);
  assert.match(editorSource, /columns === 1 \? 'Spalte' : 'Spalten'/);
  assert.match(editorSource, /ed\.commands\.insertPageLayout\(columns\)/);
  assert.match(editorSource, /ed\.commands\.setPageLayoutColumns\(columns\)/);
  assert.match(editorSource, /Darüber einfügen/);
  assert.match(editorSource, /Darunter einfügen/);
  assert.match(editorSource, /Layout auflösen/);
  assert.doesNotMatch(editorSource, /Layout löschen/);
  assert.match(editorSource, /\.note-editor__layout-remove \{ color: var\(--pm-danger/);
  assert.match(editorSource, /\.note-editor__layout-remove \.note-editor__toolbar-dropitem-glyph \{ color: currentColor; \}/);
  assert.match(layoutNodeSource, /Backspace: \(\) => this\.editor\.commands\.deleteEmptyPageLayout\(\)/);
  assert.match(layoutNodeSource, /Delete: \(\) => this\.editor\.commands\.deleteEmptyPageLayout\(\)/);
});

test('new layouts contain only independent empty columns', () => {
  const singleColumnLayout = createNotePageLayout(1);
  assert.equal(notePageLayoutColumnCount(singleColumnLayout), 1);
  assert.equal(singleColumnLayout.content.length, 1);

  const layout = createNotePageLayout(3);
  assert.equal(notePageLayoutColumnCount(layout), 3);
  assert.equal(layout.content.length, 3);
  assert.deepEqual(layout.content[0].content, [{ type: 'paragraph' }]);
  assert.notEqual(layout.content[0].content, layout.content[1].content);
});

test('resizing and dissolving one layout preserves its content in reading order', () => {
  const layout = createNotePageLayout(3);
  layout.content[0].content = [paragraph('A')];
  layout.content[1].content = [paragraph('B')];
  layout.content[2].content = [paragraph('C')];

  const expanded = resizeNotePageLayout(layout, 5);
  assert.equal(notePageLayoutColumnCount(expanded), 5);
  assert.equal(expanded.content[2].content[0].content[0].text, 'C');

  const reduced = resizeNotePageLayout(expanded, 2);
  assert.equal(notePageLayoutColumnCount(reduced), 2);
  assert.deepEqual(
    reduced.content[1].content.map((node) => node.content?.[0]?.text || ''),
    ['B', 'C'],
  );
  assert.deepEqual(
    flattenNotePageLayout(reduced).map((node) => node.content?.[0]?.text || ''),
    ['A', 'B', 'C'],
  );
});

test('layout is a normal block and its height is content-driven', () => {
  assert.match(documentSource, /content: 'block\+'/);
  assert.match(layoutNodeSource, /name: 'pageLayout'[\s\S]*?group: 'block'/);
  assert.match(layoutNodeSource, /content: 'layoutColumn\{1,5\}'/);
  assert.match(layoutNodeSource, /name: 'layoutColumn'[\s\S]*?content: 'block\+'/);
  assert.match(editorSource, /Frei platzierbare Spaltenblöcke/);
  assert.doesNotMatch(
    editorSource,
    /\[data-page-layout\][\s\S]{0,220}min-height|\[data-layout-column\][\s\S]{0,180}min-height/,
  );
  assert.doesNotMatch(
    previewSource,
    /\[data-page-layout\][\s\S]{0,180}min-height|\[data-layout-column\][\s\S]{0,180}min-height/,
  );
  assert.match(editorSource, /\[data-page-layout\]\[data-columns="1"\]/);
  assert.match(previewSource, /\[data-page-layout\]\[data-columns="1"\]/);
});

test('TipTap inserts multiple layouts among ordinary text blocks', () => {
  const editor = editorWith([paragraph('Vorher'), paragraph('Nachher')]);

  editor.commands.setTextSelection(1);
  assert.equal(editor.commands.insertPageLayout(3), true);
  assert.deepEqual(editor.getJSON().content.map((node) => node.type), [
    'pageLayout',
    'paragraph',
    'paragraph',
  ]);
  assert.equal(notePageLayoutColumnCount(editor.getJSON().content[0]), 3);

  // Der Einfügebefehl setzt die Auswahl in die erste leere Spalte. Von dort
  // kann ein weiterer Layoutblock direkt ober- oder unterhalb entstehen.
  assert.equal(editor.commands.insertPageLayoutAdjacent('after'), true);
  assert.deepEqual(editor.getJSON().content.map((node) => node.type), [
    'pageLayout',
    'pageLayout',
    'paragraph',
    'paragraph',
  ]);
  assert.equal(editor.commands.setPageLayoutColumns(5), true);
  assert.equal(notePageLayoutColumnCount(editor.getJSON().content[1]), 5);
  editor.destroy();
});

test('dissolving a layout keeps surrounding text and column content', () => {
  const layout = createNotePageLayout(2);
  layout.content[0].content = [paragraph('Links')];
  layout.content[1].content = [paragraph('Rechts')];
  const editor = editorWith([paragraph('Davor'), layout, paragraph('Danach')]);

  // Position 10 liegt in der ersten Layoutspalte hinter dem ersten Absatz.
  let layoutPosition = null;
  editor.state.doc.forEach((node, offset) => {
    if (node.type.name === 'pageLayout') layoutPosition = offset;
  });
  editor.commands.setTextSelection(layoutPosition + 3);
  assert.equal(editor.commands.unsetPageLayout(), true);
  assert.deepEqual(
    editor.getJSON().content.map((node) => node.content?.[0]?.text || ''),
    ['Davor', 'Links', 'Rechts', 'Danach'],
  );
  editor.destroy();
});

test('caret deletion removes an empty layout and keeps surrounding text', () => {
  const editor = editorWith([
    paragraph('Davor'),
    createNotePageLayout(2),
    paragraph('Danach'),
  ]);
  let layoutPosition = null;
  editor.state.doc.forEach((node, offset) => {
    if (node.type.name === 'pageLayout') layoutPosition = offset;
  });

  editor.commands.setTextSelection(layoutPosition + 3);
  assert.equal(editor.commands.deleteEmptyPageLayout(), true);
  assert.deepEqual(
    editor.getJSON().content.map((node) => node.content?.[0]?.text || ''),
    ['Davor', 'Danach'],
  );
  editor.destroy();
});

test('caret deletion cannot remove a layout before its text is empty', () => {
  const layout = createNotePageLayout(2);
  layout.content[0].content = [paragraph('Bleibt erhalten')];
  const editor = editorWith([layout]);

  editor.commands.setTextSelection(3);
  assert.equal(editor.commands.deleteEmptyPageLayout(), false);
  assert.equal(editor.getJSON().content[0].type, 'pageLayout');
  assert.equal(editor.getJSON().content[0].content[0].content[0].content[0].text, 'Bleibt erhalten');
  editor.destroy();
});

test('exports preserve each layout block in HTML and reading order in Markdown', () => {
  const first = createNotePageLayout(2);
  first.content[0].content = [paragraph('Spalte eins')];
  first.content[1].content = [paragraph('Spalte zwei')];
  const second = createNotePageLayout(3);
  const single = createNotePageLayout(1);
  const body = {
    type: 'doc',
    content: [paragraph('Davor'), first, paragraph('Dazwischen'), second, single],
  };

  const markdown = noteToMarkdown({ title: 'Layouts', body });
  const html = noteToPrintableHtml({ title: 'Layouts', body });

  assert.match(markdown, /Davor\n\nSpalte eins\n\nSpalte zwei\n\nDazwischen/);
  assert.equal((html.match(/class="page-layout /g) || []).length, 3);
  assert.match(html, /class="page-layout page-layout-1"/);
  assert.match(html, /class="page-layout page-layout-2"/);
  assert.match(html, /class="page-layout page-layout-3"/);
  assert.match(html, /<section class="layout-column"><p>Spalte eins<\/p><\/section>/);
});

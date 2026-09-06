import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import {
  noteMarkdownToSafeHtml,
  noteMarkdownToTipTap,
  parseNoteMarkdown,
} from '../src/utils/noteMarkdown.js';
import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';

const editorSource = await readNoteEditorSource();
const previewSource = fs.readFileSync(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const packageJson = JSON.parse(fs.readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

const tableBody = {
  type: 'doc',
  content: [{
    type: 'table',
    content: [
      {
        type: 'tableRow',
        content: [
          { type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Dokument' }] }] },
          { type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Status' }] }] },
        ],
      },
      {
        type: 'tableRow',
        content: [
          { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Angebot | 2026' }] }] },
          { type: 'tableCell', attrs: { colspan: 1, rowspan: 1 }, content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Geprüft', marks: [{ type: 'bold' }] }] }] },
        ],
      },
    ],
  }],
};

test('tables are available in the editor toolbar, slash menu, and read-only preview', () => {
  assert.equal(packageJson.dependencies['@tiptap/extension-table'], '3.30.2');
  assert.match(editorSource, /import \{ TableKit \} from '@tiptap\/extension-table'/);
  assert.match(editorSource, /TableKit\.configure\(\{[\s\S]*?resizable:\s*true/);
  assert.match(previewSource, /TableKit\.configure\(\{ table: \{ resizable: false, renderWrapper: true \} \}\)/);
  assert.match(editorSource, /const insertItems = \[[\s\S]*?key: 'table'[\s\S]*?label: 'Tabelle'[\s\S]*?action: 'table'/);
  assert.match(editorSource, /key: 'table'[\s\S]*?label: 'Tabelle'[\s\S]*?kind: 'table-menu'/);
  assert.match(editorSource, /insertTable\(\{[\s\S]*?withHeaderRow: tableMenu\.withHeaderRow/);
  assert.match(editorSource, /withHeaderColumn:[\s\S]*?false/);
  assert.match(editorSource, /if \(tableMenu\.withHeaderColumn\) chain\.toggleHeaderColumn\(\)/);
  assert.match(editorSource, /Erste Spalte als Kopfspalte/);
  assert.match(editorSource, /role="radiogroup" aria-label="Tabellenkopf wählen"/);
  assert.match(editorSource, /function selectTableHeaderMode\(mode\) \{[\s\S]*?withHeaderRow = mode !== 'column';[\s\S]*?withHeaderColumn = mode === 'column';/);
  assert.match(editorSource, /addRowAfter:[\s\S]*?addColumnAfter:[\s\S]*?toggleHeaderRow:[\s\S]*?toggleHeaderColumn:[\s\S]*?deleteTable:/);
  assert.match(editorSource, /aria-label="Tabellenaktionen öffnen"/);
  assert.match(editorSource, /function openTableMenuFromHandle\(\)/);
  assert.match(editorSource, /target\.closest\('\.tableWrapper'\)/);
  assert.match(editorSource, /\.pm-table-handle/);
  assert.match(editorSource, /prefers-reduced-motion: reduce[\s\S]*?\.pm-table-handle/);
  assert.match(editorSource, /\.pm-table-menu__actions button\.is-danger \{[\s\S]*?grid-column: 1 \/ -1/);
  assert.match(editorSource, /\.selectedCell::after/);
});

test('AI markdown tables become structured editable TipTap tables', () => {
  const markdown = '| Dokument | Status |\n| --- | --- |\n| Angebot | **Geprüft** |';
  const blocks = parseNoteMarkdown(markdown);
  const content = noteMarkdownToTipTap(markdown);
  const html = noteMarkdownToSafeHtml(markdown);

  assert.equal(blocks[0].type, 'table');
  assert.equal(blocks[0].header.length, 2);
  assert.equal(content[0].type, 'table');
  assert.equal(content[0].content[0].content[0].type, 'tableHeader');
  assert.equal(content[0].content[1].content[1].type, 'tableCell');
  assert.deepEqual(content[0].content[1].content[1].content[0].content[0].marks, [{ type: 'bold' }]);
  assert.match(html, /<table><thead><tr><th>Dokument<\/th><th>Status<\/th><\/tr><\/thead>/);
  assert.match(html, /<td><strong>Geprüft<\/strong><\/td>/);
});

test('AI text generated from a slash command stays inside the active table cell', () => {
  assert.match(editorSource, /DIRECT_AI_CONTAINER_TYPES = new Set\(\[[\s\S]*?'tableCell',[\s\S]*?'tableHeader'/);
  assert.match(editorSource, /aiPrompt\.targetContainerType = directTarget\?\.type \?\? ''/);
  assert.match(editorSource, /Number\.isInteger\(aiPrompt\.targetContainerFrom\)/);
  assert.match(editorSource, /insertDirectAIResult\(ed, replaceEmptyParagraph/);
});

test('note exports preserve tables in Markdown and printable HTML', () => {
  const markdown = noteToMarkdown({ title: 'Prüfung', body: tableBody });
  const html = noteToPrintableHtml({ title: 'Prüfung', body: tableBody });

  assert.match(markdown, /\| Dokument \| Status \|/);
  assert.match(markdown, /\| --- \| --- \|/);
  assert.match(markdown, /\| Angebot \\\| 2026 \| \*\*Geprüft\*\* \|/);
  assert.match(html, /<div class="table-wrap"><table><thead>/);
  assert.match(html, /<th>\s*<p>Dokument<\/p>\s*<\/th>/);
  assert.match(html, /<td>\s*<p><strong>Geprüft<\/strong><\/p>\s*<\/td>/);
  assert.match(html, /table \{ width: 100%; border-collapse: collapse;/);
});

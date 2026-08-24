import assert from 'node:assert/strict';
import test from 'node:test';

import {
  noteExportFilename,
  noteToMarkdown,
  noteToPrintableHtml,
} from '../src/utils/noteExport.js';

test('note export preserves formatting and PaperMind source references', () => {
  const markdown = noteToMarkdown({
    title: 'Recherche & Überblick',
    body: {
      type: 'doc',
      attrs: {
        linkedDocument: { id: 'doc-main', title: 'Grundlage.pdf' },
      },
      content: [
        {
          type: 'heading',
          attrs: { level: 2 },
          content: [{ type: 'text', text: 'Kernaussage' }],
        },
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'Wichtig', marks: [{ type: 'bold' }] },
            { type: 'text', text: ' laut ' },
            { type: 'documentChip', attrs: { docId: 'doc-main', title: 'Grundlage.pdf' } },
          ],
        },
        {
          type: 'ocrQuote',
          attrs: {
            text: 'Entscheidende Fundstelle',
            docId: 'doc-main',
            docTitle: 'Grundlage.pdf',
            page: 7,
          },
        },
      ],
    },
  });

  assert.match(markdown, /^# Recherche & Überblick/m);
  assert.match(markdown, /^## Kernaussage/m);
  assert.match(markdown, /\*\*Wichtig\*\*/);
  assert.match(markdown, /papermind:\/\/document\/doc-main\?page=7/);
  assert.match(markdown, /^## Quellen$/m);
  assert.match(markdown, /Grundlage\.pdf.*Seite 7/);
});

test('note export creates a safe Markdown filename', () => {
  assert.equal(noteExportFilename('  Meine Notiz: 2026 / Test  '), 'Meine-Notiz-2026-Test.md');
  assert.equal(noteExportFilename(''), 'Notiz.md');
});

test('printable note export renders a styled PDF source document', () => {
  const html = noteToPrintableHtml({
    title: 'PDF-Test',
    fontFamily: 'serif',
    paragraphSpacing: 'spacious',
    body: {
      type: 'doc',
      attrs: { linkedDocument: { id: 'doc-1', title: 'Quelle.pdf' } },
      content: [
        { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Abschnitt' }] },
        { type: 'paragraph', content: [{ type: 'text', text: '<sicher>' }] },
      ],
    },
  });

  assert.match(html, /<title>PDF-Test<\/title>/);
  assert.match(html, /font-family: Georgia/);
  assert.match(html, /margin-top: 1\.05em/);
  assert.match(html, /<h2>Abschnitt<\/h2>/);
  assert.match(html, /&lt;sicher&gt;/);
  assert.match(html, /<h2>Quellen<\/h2>/);
  assert.match(html, /papermind:\/\/document\/doc-1/);
});

test('callouts keep their PaperMind meaning in Markdown and PDF exports', () => {
  const body = {
    type: 'doc',
    content: [
      {
        type: 'callout',
        attrs: { kind: 'decision' },
        content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Variante B verwenden.' }] }],
      },
    ],
  };

  const markdown = noteToMarkdown({ title: 'Beschluss', body });
  const html = noteToPrintableHtml({ title: 'Beschluss', body });
  assert.match(markdown, /> \*\*✓ Entscheidung\*\*/);
  assert.match(markdown, /> Variante B verwenden\./);
  assert.match(html, /class="callout callout-decision"/);
  assert.match(html, /✓ Entscheidung/);
  assert.match(html, /Variante B verwenden\./);
});

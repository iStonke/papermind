import test from 'node:test';
import assert from 'node:assert/strict';
import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';
const note = { title: 'Test', body: { type: 'doc', content: [{ type: 'collapsibleSection', attrs: { title: '<Details>', open: false }, content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Verborgener Inhalt' }] }] }] } };
test('collapsed sections keep escaped titles and content in Markdown exports', () => {
  const md = noteToMarkdown(note);
  assert.match(md, /<details data-note-section><summary>&lt;Details&gt;<\/summary>/);
  assert.match(md, /Verborgener Inhalt/);
});
test('print exports include collapsed content without a hidden details element', () => {
  const html = noteToPrintableHtml(note);
  assert.match(html, /<h3>&lt;Details&gt;<\/h3>/);
  assert.match(html, /Verborgener Inhalt/);
  assert.doesNotMatch(html, /<details/);
});

import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

import { NoteHighlight } from '../src/components/notes/nodes/noteHighlight.js';
import {
  NOTE_HIGHLIGHT_COLORS,
  normalizeNoteHighlightColor,
  noteHighlightInlineStyle,
} from '../src/utils/noteHighlights.js';
import { noteToMarkdown, noteToPrintableHtml } from '../src/utils/noteExport.js';

const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const previewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);
const highlightSource = await readFile(
  new URL('../src/components/notes/nodes/noteHighlight.js', import.meta.url),
  'utf8',
);

test('text marker offers five safe colors and a remove action', () => {
  assert.deepEqual(
    NOTE_HIGHLIGHT_COLORS.map((color) => color.value),
    ['yellow', 'green', 'blue', 'pink', 'purple'],
  );
  assert.equal(normalizeNoteHighlightColor('blue'), 'blue');
  assert.equal(normalizeNoteHighlightColor('javascript:red'), 'yellow');
  assert.equal(noteHighlightInlineStyle('pink'), 'background-color: #fbcfe8; color: #172126;');
  // Textmarker lebt jetzt in der Auswahl-Bubble (Variante A), nicht mehr oben.
  assert.match(editorSource, /key: 'highlight',\s*label: 'Textmarker',\s*icon: 'mdi-format-color-highlight'/);
  assert.match(editorSource, /aria-label="Textmarkerfarbe"/);
  assert.match(editorSource, /v-for="color in NOTE_HIGHLIGHT_COLORS"/);
  assert.match(editorSource, /Markierung entfernen/);
  assert.match(previewSource, /NoteHighlight/);
});

test('text marker persists its selected color and can be removed', () => {
  const editor = new Editor({
    extensions: [StarterKit, NoteHighlight],
    content: {
      type: 'doc',
      content: [{
        type: 'paragraph',
        content: [{ type: 'text', text: 'Markierter Text' }],
      }],
    },
  });

  editor.commands.setTextSelection({ from: 1, to: 10 });
  assert.equal(editor.commands.setNoteHighlight('blue'), true);
  const [highlightMark] = editor.getJSON().content[0].content[0].marks;
  assert.equal(highlightMark.type, 'highlight');
  assert.equal(highlightMark.attrs.color, 'blue');
  assert.match(highlightSource, /'data-highlight': color/);
  assert.match(highlightSource, /style: noteHighlightInlineStyle\(color\)/);

  assert.equal(editor.commands.unsetNoteHighlight(), true);
  assert.equal(editor.getJSON().content[0].content[0].marks, undefined);
  editor.destroy();
});

test('Markdown and printable export preserve text-marker colors', () => {
  const body = {
    type: 'doc',
    content: [{
      type: 'paragraph',
      content: [{
        type: 'text',
        text: 'Wichtig',
        marks: [{ type: 'highlight', attrs: { color: 'green' } }],
      }],
    }],
  };

  const markdown = noteToMarkdown({ title: 'Marker', body });
  const html = noteToPrintableHtml({ title: 'Marker', body });
  for (const output of [markdown, html]) {
    assert.match(output, /<mark data-highlight="green"/);
    assert.match(output, /background-color: #bbf7d0/);
    assert.match(output, />Wichtig<\/mark>/);
  }
});

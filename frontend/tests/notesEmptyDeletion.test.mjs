import assert from 'node:assert/strict';
import test from 'node:test';

import { isNoteEmpty } from '../src/stores/notes.js';

test('note emptiness ignores placeholder paragraphs and whitespace', () => {
  assert.equal(isNoteEmpty({
    title: '  ',
    body_json: {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: ' \n ' }] }],
    },
  }), true);
});

test('a custom title or visible note text keeps the note recoverable', () => {
  assert.equal(isNoteEmpty({ title: 'Gedanke', preview: '' }), false);
  assert.equal(isNoteEmpty({ title: '', preview: 'Noch einmal prüfen' }), false);
  assert.equal(isNoteEmpty({
    title: '',
    body_json: {
      type: 'doc',
      content: [{ type: 'documentChip', attrs: { title: 'Rechnung.pdf' } }],
    },
  }), false);
});

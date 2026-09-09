import test from 'node:test';
import assert from 'node:assert/strict';

import { buildQuickNotePayload, QUICK_NOTE_TITLE_MAX_LENGTH } from '../src/utils/quickNote.js';

test('quick note uses the first line as title and remaining lines as paragraphs', () => {
  assert.deepEqual(buildQuickNotePayload('Besprechung\nEntscheidung festhalten\n\nNächster Schritt'), {
    title: 'Besprechung',
    body_json: {
      type: 'doc',
      content: [
        { type: 'paragraph', content: [{ type: 'text', text: 'Entscheidung festhalten' }] },
        { type: 'paragraph' },
        { type: 'paragraph', content: [{ type: 'text', text: 'Nächster Schritt' }] },
      ],
    },
  });
});

test('quick note creates a valid empty body for a title-only note', () => {
  assert.deepEqual(buildQuickNotePayload('Nur ein Gedanke'), {
    title: 'Nur ein Gedanke',
    body_json: { type: 'doc', content: [{ type: 'paragraph' }] },
  });
  assert.equal(buildQuickNotePayload(' \n '), null);
});

test('quick note normalizes line endings and respects the title limit', () => {
  const payload = buildQuickNotePayload(`${'x'.repeat(QUICK_NOTE_TITLE_MAX_LENGTH + 20)}\r\nText`);
  assert.equal(payload.title.length, QUICK_NOTE_TITLE_MAX_LENGTH);
  assert.equal(payload.body_json.content[0].content[0].text, 'Text');
});

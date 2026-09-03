import assert from 'node:assert/strict';
import test from 'node:test';

import {
  noteAITextForCodeBlock,
  noteMarkdownToSafeHtml,
  noteMarkdownToTipTap,
  parseNoteMarkdown,
} from '../src/utils/noteMarkdown.js';

test('AI code output drops an outer Markdown fence but preserves the code itself', () => {
  assert.equal(
    noteAITextForCodeBlock('```js\nconst answer = 42;\n```'),
    'const answer = 42;',
  );
  assert.equal(noteAITextForCodeBlock('return value < limit;'), 'return value < limit;');
});

test('AI markdown bullet output becomes a structured list', () => {
  const markdown = '- Erster Punkt\n- **Wichtiger** Punkt\n- Dritter Punkt';
  const blocks = parseNoteMarkdown(markdown);
  const tipTap = noteMarkdownToTipTap(markdown);

  assert.equal(blocks[0].type, 'bulletList');
  assert.equal(blocks[0].items.length, 3);
  assert.equal(tipTap[0].type, 'bulletList');
  assert.equal(tipTap[0].content[1].type, 'listItem');
  assert.deepEqual(
    tipTap[0].content[1].content[0].content[0].marks,
    [{ type: 'bold' }],
  );
});

test('ordered AI markdown retains its start and inline formatting', () => {
  const tipTap = noteMarkdownToTipTap('3. Eins\n4. `Zwei`');

  assert.equal(tipTap[0].type, 'orderedList');
  assert.equal(tipTap[0].attrs.start, 3);
  assert.deepEqual(
    tipTap[0].content[1].content[0].content[0].marks,
    [{ type: 'code' }],
  );
});

test('printable AI markdown is escaped before list markup is added', () => {
  const html = noteMarkdownToSafeHtml('- <script>alert(1)</script>\n- **Sicher**');

  assert.match(html, /^<ul>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /<strong>Sicher<\/strong>/);
});

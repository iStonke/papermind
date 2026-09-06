import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { historyChangedRange } from '../src/components/notes/extensions/historyFlash.js';

const editorSource = await readNoteEditorSource();
const extensionSource = await readFile(
  new URL('../src/components/notes/extensions/historyFlash.js', import.meta.url),
  'utf8',
);

function mockDoc({ size = 20, start = null, end = null } = {}) {
  return {
    content: {
      size,
      findDiffStart: () => start,
      findDiffEnd: () => end,
    },
  };
}

test('undo and redo highlight exactly the changed range', () => {
  const before = mockDoc({ start: 4, end: { a: 8, b: 11 } });
  const after = mockDoc({ size: 18 });
  assert.deepEqual(historyChangedRange(before, after), { from: 4, to: 11 });
  assert.equal(historyChangedRange(mockDoc(), after), null);
});

test('removed content does not inject a second caret-like marker', () => {
  const before = mockDoc({ start: 7, end: { a: 12, b: 7 } });
  const after = mockDoc({ size: 14 });
  assert.deepEqual(historyChangedRange(before, after), { from: 7, to: 7 });
  assert.doesNotMatch(extensionSource, /Decoration\.widget/);
  assert.doesNotMatch(extensionSource, /pm-history-flash-point/);
  assert.doesNotMatch(extensionSource, /pm-history-flash-caret/);
});

test('the editor disables ProseMirror’s synthetic gap cursor', () => {
  assert.match(editorSource, /StarterKit\.configure\(\{[\s\S]*?gapcursor:\s*false/);
  assert.doesNotMatch(editorSource, /ProseMirror-gapcursor/);
});

test('history feedback follows ProseMirror history transactions without changing note content', () => {
  assert.match(editorSource, /isHistoryTransaction\(transaction\)/);
  assert.match(editorSource, /historyChangedRange\(transaction\.before, transaction\.doc\)/);
  assert.match(editorSource, /showHistoryFlash\(ed, range\)/);
  assert.match(editorSource, /clearHistoryFlash\(ed\)/);
  assert.match(editorSource, /transaction\.docChanged \|\| transaction\.selectionSet\)[\s\S]*?dismissHistoryFlash\(ed\)/);
  assert.match(extensionSource, /setMeta\('addToHistory', false\)/);
  assert.match(editorSource, /@keyframes pm-history-change-flash/);
  assert.match(editorSource, /prefers-reduced-motion: reduce[\s\S]*?pm-history-flash/);
  assert.match(editorSource, /pm-no-animations[\s\S]*?pm-history-flash/);
});

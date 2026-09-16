import test from 'node:test';
import assert from 'node:assert/strict';
import { TextSelection, AllSelection } from '@tiptap/pm/state';
import { createTestEditor } from './helpers/noteEditorHarness.mjs';
import { selectedWordCount, wordCountLabel } from '../src/utils/noteWordCount.js';

test('word count follows selection and returns to total when selection collapses', () => {
  const editor = createTestEditor('eins zwei drei');
  assert.equal(selectedWordCount(editor.state), null);
  editor.commands.setTextSelection({ from: 1, to: 10 });
  assert.equal(selectedWordCount(editor.state), 2);
  assert.equal(wordCountLabel(3, selectedWordCount(editor.state)), '2 von 3 Wörtern');
  editor.commands.setTextSelection(1);
  assert.equal(wordCountLabel(3, selectedWordCount(editor.state)), '3 Wörter');
});

test('selection across paragraphs counts words separately and supports select all', () => {
  const editor = createTestEditor('', { type: 'doc', content: [
    { type: 'paragraph', content: [{ type: 'text', text: 'eins zwei' }] },
    { type: 'paragraph', content: [{ type: 'text', text: 'drei vier' }] },
  ] });
  editor.view.dispatch(editor.state.tr.setSelection(new AllSelection(editor.state.doc)));
  assert.equal(selectedWordCount(editor.state), 4);
  editor.view.dispatch(editor.state.tr.setSelection(TextSelection.create(editor.state.doc, 6, 16)));
  assert.equal(selectedWordCount(editor.state), 2);
  assert.equal(wordCountLabel(1), '1 Wort');
  assert.equal(wordCountLabel(0), '0 Wörter');
});

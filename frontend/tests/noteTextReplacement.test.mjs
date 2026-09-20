import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyTextReplacement,
  findTextReplacement,
  textReplacementDecorations,
} from '../src/components/notes/extensions/textReplacement.js';
import { createTestEditor } from './helpers/noteEditorHarness.mjs';

function editorWithText(text) {
  const editor = createTestEditor(text);
  editor.commands.setTextSelection(editor.state.doc.content.size - 1);
  return editor;
}

test('text replacement matches the token directly before the cursor', () => {
  const editor = editorWithText('Viele Grüße MFG');

  const match = findTextReplacement(editor.state, [
    { shortcut: 'MFG', replacement: 'Mit freundlichen Grüßen', enabled: true },
  ]);

  assert.equal(match.replacement, 'Mit freundlichen Grüßen');
  assert.equal(editor.state.doc.textBetween(match.from, match.to), 'MFG');
});

test('text replacement is exact and ignores disabled entries', () => {
  const editor = editorWithText('mfg');
  const replacements = [
    { shortcut: 'MFG', replacement: 'Falsch wegen Großschreibung', enabled: true },
    { shortcut: 'mfg', replacement: 'Deaktiviert', enabled: false },
  ];

  assert.equal(findTextReplacement(editor.state, replacements), null);
});

test('applying a replacement changes only the shortcut', () => {
  const editor = editorWithText('Grußformel: MFG');
  const view = {
    get state() { return editor.state; },
    dispatch: (transaction) => editor.view.dispatch(transaction),
  };

  assert.equal(applyTextReplacement(view, [
    { shortcut: 'MFG', replacement: 'Mit freundlichen Grüßen', enabled: true },
  ]), true);
  assert.equal(editor.getText(), 'Grußformel: Mit freundlichen Grüßen');
});

test('an available replacement decorates the shortcut and adds an inline hint', () => {
  const editor = editorWithText('MFG');
  const decorations = textReplacementDecorations(editor.state, [
    { shortcut: 'MFG', replacement: 'Mit freundlichen Grüßen', enabled: true },
  ]).find();

  assert.equal(decorations.length, 2);
  assert.ok(decorations.some((decoration) => decoration.type.attrs?.class === 'pm-text-replacement-trigger'));
  assert.ok(decorations.some((decoration) => decoration.type.spec?.key?.startsWith('text-replacement:')));
});

import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick, reactive, shallowRef } from 'vue';
import { useNoteLinks } from '../src/components/notes/composables/useNoteLinks.js';
import { useNoteTables } from '../src/components/notes/composables/useNoteTables.js';
import { useNoteReferences } from '../src/components/notes/composables/useNoteReferences.js';
import { createNoteOverlayCoordinator } from '../src/components/notes/composables/noteOverlayCoordinator.js';
import { mountController, createTestEditor } from './helpers/noteEditorHarness.mjs';

function setup(factory) {
  const editor = shallowRef(createTestEditor());
  const props = reactive({ noteId: 'one' });
  const overlays = createNoteOverlayCoordinator();
  const mounted = mountController(() => factory({
    editor, props, overlays, surfaceEl: shallowRef(null),
    clampMenuLeft: (left) => left, getTargets: () => [],
  }));
  return { ...mounted, editor, props, overlays };
}

test('link editing preserves the captured range when focus moves and remains undoable', () => {
  const { controller: c, editor, unmount } = setup(useNoteLinks);
  editor.value.commands.setTextSelection({ from: 1, to: 9 });
  c.openLinkEditor();
  editor.value.commands.setTextSelection(14);
  c.linkEditor.href = 'https://example.org/angebot';
  c.applyLink();
  const paragraph = editor.value.state.doc.firstChild;
  assert.equal(paragraph.firstChild.text, 'Original');
  assert.equal(paragraph.firstChild.marks[0].attrs.href, 'https://example.org/angebot');
  assert.equal(paragraph.lastChild.text, ' text');
  assert.equal(paragraph.lastChild.marks.length, 0);
  editor.value.commands.undo();
  assert.equal(editor.value.getText(), 'Original text');
  assert.equal(editor.value.state.doc.firstChild.firstChild.marks.length, 0);
  unmount();
});

test('invalid links leave the document unchanged and switching notes closes the form', async () => {
  const { controller: c, editor, props, unmount } = setup(useNoteLinks);
  c.openLinkEditor();
  c.linkEditor.href = 'javascript:alert(1)';
  const original = editor.value.state.doc.toJSON();
  c.applyLink();
  assert.ok(c.linkEditor.error);
  assert.deepEqual(editor.value.state.doc.toJSON(), original);
  props.noteId = 'two';
  await nextTick();
  assert.equal(c.linkEditor.open, false);
  unmount();
});

test('table size keyboard navigation stays within the visible grid and Escape dismisses it', () => {
  const { controller: c, unmount } = setup(useNoteTables);
  c.openTableMenu('insert');
  for (let i = 0; i < 10; i++) {
    assert.equal(c.handleTableKeydown({ key: 'ArrowLeft' }), true);
    assert.equal(c.handleTableKeydown({ key: 'ArrowDown' }), true);
  }
  assert.equal(c.tableMenu.cols, 1);
  assert.equal(c.tableMenu.rows, 5);
  assert.equal(c.handleTableKeydown({ key: 'x' }), false);
  assert.equal(c.handleTableKeydown({ key: 'Escape' }), true);
  assert.equal(c.tableMenu.open, false);
  unmount();
});

test('reference filtering resets an out-of-range cursor and picks the visible result', async () => {
  const { controller: c, props, unmount } = setup(useNoteReferences);
  const targets = [{ id: 'one', label: 'Versicherung' }, { id: 'two', label: 'Steuer 2024' }];
  const chosen = [];
  c.openPicker('target', targets, (target) => chosen.push(target.id));
  c.handlePickerKeydown({ key: 'ArrowDown' });
  c.picker.query = 'Steuer';
  await nextTick();
  assert.equal(c.picker.index, 0);
  assert.equal(c.handlePickerKeydown({ key: 'Enter' }), true);
  assert.deepEqual(chosen, ['two']);
  c.openPicker('target', targets, () => assert.fail('closed picker must not select'));
  props.noteId = 'two';
  await nextTick();
  assert.equal(c.handlePickerKeydown({ key: 'Enter' }), false);
  unmount();
});

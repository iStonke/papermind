import assert from 'node:assert/strict';
import test from 'node:test';
import { reactive, shallowRef } from 'vue';
import { useNoteCleanup } from '../src/components/notes/composables/useNoteCleanup.js';
import { createNoteOverlayCoordinator } from '../src/components/notes/composables/noteOverlayCoordinator.js';
import { cleanupSource, cleanupReplacement } from '../src/utils/noteCleanupContent.js';
import { createTestEditor, mountController } from './helpers/noteEditorHarness.mjs';

const paragraph = (text) => ({ type: 'paragraph', content: [{ type: 'text', text }] });
function setup(body, answer) {
  const editor = shallowRef(createTestEditor('', body));
  const payloads = [];
  const mounted = mountController(() => useNoteCleanup({
    editor, props: reactive({ noteId: 'one', aiAvailable: true }),
    overlays: createNoteOverlayCoordinator(), onCheckpoint() {},
    stream: async (payload, { onEvent }) => { payloads.push(payload); onEvent({ type: 'delta', text: answer }); },
  }));
  return { ...mounted, editor: editor.value, payloads };
}

test('selected paragraph is previewed as tasks and only changes on apply; undo restores the exact document', async () => {
  const body = { type: 'doc', content: [paragraph('Davor'), paragraph('milch kaufen und brot holen'), paragraph('Danach')] };
  const { controller: c, editor, unmount } = setup(body, '⟦1⟧\n- [ ] Milch kaufen\n- [ ] Brot holen');
  const original = editor.state.doc.toJSON();
  const start = editor.state.doc.firstChild.nodeSize;
  editor.commands.setTextSelection({ from: start + 1, to: start + editor.state.doc.child(1).nodeSize - 1 });
  await c.startCleanup();
  assert.deepEqual(editor.state.doc.toJSON(), original);
  assert.match(c.cleanupDraftHtml.value, /data-type="taskList"/);
  assert.equal(c.cleanupCanApply.value, true);
  c.applyCleanup();
  editor.state.doc.check();
  assert.equal(editor.state.doc.child(1).type.name, 'taskList');
  assert.equal(editor.state.doc.child(1).childCount, 2);
  assert.deepEqual(editor.state.doc.firstChild.toJSON(), original.content[0]);
  assert.deepEqual(editor.state.doc.lastChild.toJSON(), original.content[2]);
  c.restoreCleanupOriginal();
  assert.deepEqual(editor.state.doc.toJSON(), original);
  unmount();
});

test('partial selection gains inline emphasis without changing neighboring text or its marks', async () => {
  const body = { type: 'doc', content: [{ type: 'paragraph', content: [
    { type: 'text', text: 'Davor ', marks: [{ type: 'italic' }] },
    { type: 'text', text: 'morgen' },
    { type: 'text', text: ' danach', marks: [{ type: 'bold' }] },
  ] }] };
  const { controller: c, editor, payloads, unmount } = setup(body, '⟦1⟧ **Morgen**');
  editor.commands.setTextSelection({ from: 7, to: 13 });
  await c.startCleanup();
  assert.match(payloads[0].selected_text, /Nur Inline/);
  c.applyCleanup();
  assert.equal(editor.getText(), 'Davor Morgen danach');
  assert.deepEqual(editor.state.doc.firstChild.firstChild.marks.map((mark) => mark.type.name), ['italic']);
  assert.deepEqual(editor.state.doc.firstChild.lastChild.marks.map((mark) => mark.type.name), ['bold']);
  unmount();
});

test('an existing checked task remains checked while its text is cleaned', async () => {
  const body = { type: 'doc', content: [{ type: 'taskList', content: [{ type: 'taskItem', attrs: { checked: true }, content: [paragraph('milch gekauft')] }] }] };
  const { controller: c, editor, unmount } = setup(body, '⟦1⟧ Milch **gekauft**.');
  editor.commands.setTextSelection({ from: 3, to: 16 });
  await c.startCleanup(); c.applyCleanup();
  assert.equal(editor.state.doc.firstChild.firstChild.attrs.checked, true);
  assert.equal(editor.state.doc.firstChild.firstChild.textContent, 'Milch gekauft.');
  editor.state.doc.check();
  unmount();
});

test('format-only edits during review invalidate the captured target', async () => {
  const { controller: c, editor, unmount } = setup({ type: 'doc', content: [paragraph('Original')] }, '⟦1⟧ **Original**.');
  await c.startCleanup();
  editor.view.dispatch(editor.state.tr.addMark(1, 9, editor.state.schema.marks.italic.create()));
  const changed = editor.state.doc.toJSON();
  c.applyCleanup();
  assert.match(c.cleanup.error, /geändert/);
  assert.deepEqual(editor.state.doc.toJSON(), changed);
  unmount();
});

test('block formatting is rejected for partial selections; decorative blocks are rejected for cleanup', async () => {
  const { controller: c, editor, unmount } = setup({ type: 'doc', content: [paragraph('Davor morgen danach')] }, '⟦1⟧\n- Morgen');
  editor.commands.setTextSelection({ from: 7, to: 13 });
  await c.startCleanup();
  assert.equal(c.cleanupCanApply.value, false);
  assert.match(c.cleanupValidation.value.error, /vollständigen Absatz/);
  c.discardCleanup();
  assert.equal(editor.getText(), 'Davor morgen danach');
  const target = { from: 1, to: 7, source: 'Text', originalContent: [{ type: 'text', text: 'Text' }], allowBlocks: true };
  assert.throws(() => cleanupReplacement(target, '> [!IMPORTANT]\n> Text'), /beschränken/);
  unmount();
});

test('existing highlight survives text improvement without leaking HTML into the model input', () => {
  const originalContent = [{ type: 'text', text: 'termin morgen', marks: [{ type: 'highlight', attrs: { color: 'yellow' } }] }];
  const source = cleanupSource(originalContent);
  assert.equal(source, 'termin morgen');
  const replacement = cleanupReplacement({ from: 1, to: 14, source, originalContent }, 'Termin **morgen**.');
  assert.ok(replacement.content.every((node) => node.marks.some((mark) => mark.type === 'highlight')));
  assert.equal(replacement.content.map((node) => node.text).join(''), 'Termin morgen.');
});

test('escaped punctuation and combined emphasis survive cleanup conversion', () => {
  const originalContent = [{ type: 'text', text: 'Wichtig', marks: [{ type: 'bold' }, { type: 'italic' }] }, { type: 'text', text: ' * wort' }];
  const source = cleanupSource(originalContent);
  const target = { from: 1, to: 16, source, originalContent };
  const result = cleanupReplacement(target, source + '.');
  assert.deepEqual(result.content[0].marks.map((mark) => mark.type), ['bold', 'italic']);
  assert.equal(result.content.map((node) => node.text).join(''), 'Wichtig * wort.');
});

test('restoring cleanup does not undo typing that happened immediately before it', async () => {
  const { controller: c, editor, unmount } = setup({ type: 'doc', content: [paragraph('milch kaufen')] }, '⟦1⟧ Milch heute kaufen.');
  editor.view.dispatch(editor.state.tr.insertText(' heute', 13));
  const typed = editor.state.doc.toJSON();
  await c.startCleanup(); c.applyCleanup(); c.restoreCleanupOriginal();
  assert.deepEqual(editor.state.doc.toJSON(), typed);
  unmount();
});

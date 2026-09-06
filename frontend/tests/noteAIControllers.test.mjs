import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick, reactive, shallowRef } from 'vue';
import { useNoteWriting } from '../src/components/notes/composables/useNoteWriting.js';
import { useNoteCleanup } from '../src/components/notes/composables/useNoteCleanup.js';
import { createNoteOverlayCoordinator } from '../src/components/notes/composables/noteOverlayCoordinator.js';
import { mountController, createTestEditor } from './helpers/noteEditorHarness.mjs';

function setup(factory, stream) {
  const editor = shallowRef(createTestEditor());
  const props = reactive({ noteId: 'one', aiAvailable: true, aiPromptSuggestions: [] });
  const checkpoints = [];
  const overlays = createNoteOverlayCoordinator();
  const mounted = mountController(() => factory({ editor, props, overlays, stream, surfaceEl: shallowRef(null), clampMenuLeft: (left) => left, onCheckpoint: (reason) => checkpoints.push(reason) }));
  return { ...mounted, editor, props, checkpoints, overlays };
}

function deferredStream() {
  const calls = [];
  function stream(payload, options) {
    return new Promise((resolve) => calls.push({ payload, ...options, resolve }));
  }
  return { calls, stream };
}

function prepareWriting(c) { c.prepareToolbarAIPromptTarget(); c.aiPrompt.instruction = 'Zusammenfassen'; }

test('note switch cancels old writing; late deltas and finally cannot change a newer request', async () => {
  const { calls, stream } = deferredStream();
  const { controller: c, props, editor, unmount } = setup(useNoteWriting, stream);
  prepareWriting(c);
  const old = c.generateAIText();
  props.noteId = 'two';
  await nextTick();
  assert.equal(calls[0].signal.aborted, true);
  prepareWriting(c);
  const current = c.generateAIText();
  calls[0].onEvent({ type: 'delta', text: 'STALE' });
  calls[0].resolve();
  await old;
  assert.equal(c.aiPrompt.loading, true);
  assert.equal(c.aiPrompt.preview, '');
  assert.equal(editor.value.getText(), 'Original text');
  c.closeAIPrompt();
  calls[1].resolve();
  await current;
  unmount();
});

test('generated writing uses editable paragraphs, preserves attribution, and is one undoable edit', async () => {
  const { controller: c, editor, checkpoints, unmount } = setup(useNoteWriting, async (_payload, { onEvent }) => {
    onEvent({ type: 'meta', provider: 'ollama', model: 'test-model' });
    onEvent({ type: 'delta', text: 'Zusammenfassung' });
  });
  prepareWriting(c);
  await c.generateAIText();
  let block;
  editor.value.state.doc.descendants((node) => { if (node.attrs.aiGeneration) block = node; });
  assert.equal(block.type.name, 'paragraph');
  assert.equal(block.textContent, 'Zusammenfassung');
  assert.equal(block.attrs.aiGeneration.provider, 'ollama');
  assert.equal(block.attrs.aiGeneration.model, 'test-model');
  assert.deepEqual(checkpoints, ['ai']);
  editor.value.commands.undo();
  assert.equal(editor.value.getText(), 'Original text');
  assert.equal(editor.value.state.doc.childCount, 1);
  unmount();
});

test('streamed shopping list replaces the captured selection with native tasks in one undo step', async () => {
  const { controller: c, editor, checkpoints, unmount } = setup(useNoteWriting, async (_payload, { onEvent }) => {
    onEvent({ type: 'delta', text: '- [ ] Rote ' });
    onEvent({ type: 'delta', text: 'Äpfel\n- [ ] Frische Birnen' });
  });
  const original = editor.value.state.doc.toJSON();
  editor.value.commands.setTextSelection({ from: 1, to: 14 });
  prepareWriting(c);
  c.aiPrompt.instruction = 'Erstelle eine Einkaufsliste';
  await c.generateAIText();
  let tasks;
  editor.value.state.doc.descendants((node) => { if (node.type.name === 'taskList') tasks = node; });
  assert.equal(tasks.childCount, 2);
  assert.equal(tasks.firstChild.textContent, 'Rote Äpfel');
  assert.equal(tasks.lastChild.attrs.checked, false);
  assert.equal(editor.value.getText().includes('Original text'), false);
  assert.deepEqual(checkpoints, ['ai']);
  editor.value.commands.undo();
  assert.deepEqual(editor.value.state.doc.toJSON(), original);
  unmount();
});

test('generation without a body cursor replaces an empty final paragraph rather than adding a blank line', async () => {
  const { controller: c, editor, unmount } = setup(useNoteWriting, async (_payload, { onEvent }) => {
    onEvent({ type: 'delta', text: '- [ ] Kiwi' });
  });
  editor.value = createTestEditor('');
  editor.value.view.hasFocus = () => false;
  prepareWriting(c);
  c.aiPrompt.instruction = 'Einkaufsliste';
  await c.generateAIText();
  assert.equal(editor.value.state.doc.childCount, 1);
  assert.equal(editor.value.state.doc.firstChild.type.name, 'taskList');
  unmount();
});

test('selection review inserts native structure only after the requested action', async () => {
  const { controller: c, editor, unmount } = setup(useNoteWriting, async (_payload, { onEvent }) => {
    onEvent({ type: 'delta', text: '## Neuer Titel\n\n- [ ] Prüfen' });
  });
  editor.value.commands.setTextSelection({ from: 1, to: 14 });
  c.openAIPrompt();
  c.aiPrompt.instruction = 'Als Überschrift und Aufgabe strukturieren';
  await c.generateAIText();
  assert.equal(editor.value.getText(), 'Original text');
  c.applySelectionAIResult('insert');
  assert.equal(editor.value.getText().includes('Original text'), true);
  const types = [];
  editor.value.state.doc.forEach((node) => types.push(node.type.name));
  assert.ok(types.includes('heading'));
  assert.ok(types.includes('taskList'));
  assert.equal(c.aiPrompt.open, false);
  unmount();
});

test('a malformed checklist response cannot overwrite existing text with a run-on paragraph', async () => {
  const { controller: c, editor, unmount } = setup(useNoteWriting, async (_payload, { onEvent }) => {
    onEvent({ type: 'delta', text: 'Mandarine Zitrone Banane Kiwi' });
  });
  editor.value.commands.setTextSelection({ from: 1, to: 14 });
  prepareWriting(c);
  c.aiPrompt.instruction = 'Erstelle eine Einkaufsliste';
  await c.generateAIText();
  assert.equal(editor.value.getText(), 'Original text');
  assert.match(c.aiPrompt.error, /keine Aufgabenliste/);
  assert.equal(c.aiPrompt.loading, false);
  unmount();
});

test('cleanup preview and discard leave the document unchanged', async () => {
  const { calls, stream } = deferredStream();
  const { controller: c, editor, unmount } = setup(useNoteCleanup, stream);
  const original = editor.value.state.doc.toJSON();
  const pending = c.startCleanup();
  calls[0].onEvent({ type: 'delta', text: 'A proposal' });
  assert.deepEqual(editor.value.state.doc.toJSON(), original);
  c.discardCleanup();
  assert.equal(calls[0].signal.aborted, true);
  calls[0].resolve();
  await pending;
  assert.equal(c.cleanup.open, false);
  assert.deepEqual(editor.value.state.doc.toJSON(), original);
  unmount();
});

test('cleanup applies only after review and restores the original via undo', async () => {
  const { calls, stream } = deferredStream();
  const { controller: c, editor, checkpoints, unmount } = setup(useNoteCleanup, stream);
  const pending = c.startCleanup();
  calls[0].resolve();
  await pending;
  c.cleanup.draftBlocks = ['Bereinigter Text'];
  c.applyCleanup();
  assert.equal(editor.value.getText(), 'Bereinigter Text');
  assert.equal(c.cleanupRestore.open, true);
  assert.deepEqual(checkpoints, ['ai']);
  c.restoreCleanupOriginal();
  assert.equal(editor.value.getText(), 'Original text');
  assert.equal(c.cleanupRestore.open, false);
  unmount();
});

test('cleanup refuses to overwrite text changed during review', async () => {
  const { calls, stream } = deferredStream();
  const { controller: c, editor, unmount } = setup(useNoteCleanup, stream);
  const pending = c.startCleanup();
  calls[0].resolve(); await pending;
  c.cleanup.draftBlocks = ['Bereinigter Text'];
  editor.value.view.dispatch(editor.value.state.tr.insertText('Changed', 1, 9));
  const changed = editor.value.state.doc.toJSON();
  c.applyCleanup();
  assert.match(c.cleanup.error, /geändert/);
  assert.deepEqual(editor.value.state.doc.toJSON(), changed);
  unmount();
});

test('opening another feature cancels writing and unmount aborts active cleanup', async () => {
  const writingStream = deferredStream();
  const w = setup(useNoteWriting, writingStream.stream);
  prepareWriting(w.controller); const writing = w.controller.generateAIText();
  w.overlays.open('link');
  assert.equal(writingStream.calls[0].signal.aborted, true);
  writingStream.calls[0].resolve(); await writing; w.unmount();
  const cleanupStream = deferredStream();
  const c = setup(useNoteCleanup, cleanupStream.stream);
  const cleanup = c.controller.startCleanup(); c.unmount();
  assert.equal(cleanupStream.calls[0].signal.aborted, true);
  cleanupStream.calls[0].resolve(); await cleanup;
});

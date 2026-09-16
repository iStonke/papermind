import assert from 'node:assert/strict';
import test from 'node:test';
import { nextTick, reactive, shallowRef } from 'vue';
import { useNoteWriting } from '../src/components/notes/composables/useNoteWriting.js';
import { useNoteCleanup } from '../src/components/notes/composables/useNoteCleanup.js';
import { useNoteReview } from '../src/components/notes/composables/useNoteReview.js';
import { createNoteOverlayCoordinator } from '../src/components/notes/composables/noteOverlayCoordinator.js';
import { mountController, createTestEditor } from './helpers/noteEditorHarness.mjs';

function setup(factory, stream, options = {}) {
  const editor = shallowRef(createTestEditor());
  const props = reactive({ noteId: 'one', aiAvailable: true, aiPromptSuggestions: [] });
  const checkpoints = [];
  const overlays = createNoteOverlayCoordinator();
  const mounted = mountController(() => factory({ ...options, editor, props, overlays, stream, surfaceEl: shallowRef(null), clampMenuLeft: (left) => left, onCheckpoint: (reason) => checkpoints.push(reason) }));
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

// Alle Microtasks des (nicht awaiteten) stillen Retrys abarbeiten.
async function flushReview() {
  for (let i = 0; i < 12; i += 1) await Promise.resolve();
  await nextTick();
}

test('review retries once on unparseable JSON and never leaves loading stuck', async () => {
  let calls = 0;
  const stream = async (_payload, { onEvent }) => {
    calls += 1;
    onEvent({ type: 'meta', provider: 'anthropic', model: 'x' });
    onEvent({ type: 'delta', text: 'das ist kein json' });
  };
  const { controller: c, unmount } = setup(useNoteReview, stream);
  await c.startReview();
  await flushReview();
  assert.equal(calls, 2, 'genau ein stiller Neuversuch');
  assert.equal(c.review.loading, false, 'Ladezustand darf nicht hängenbleiben');
  assert.ok(c.review.error, 'nach dem Fehlversuch wird ein Fehler gezeigt');
  unmount();
});

test('review recovers on a valid second response after one bad JSON', async () => {
  let calls = 0;
  const stream = async (_payload, { onEvent }) => {
    calls += 1;
    onEvent({ type: 'meta', provider: 'anthropic', model: 'x' });
    onEvent({ type: 'delta', text: calls === 1
      ? 'kaputt'
      : JSON.stringify({ changes: [{ id: 1, cat: 'fix', anchor: 'Original', revised: 'Ursprung', reason: 'r' }] }) });
  };
  const { controller: c, unmount } = setup(useNoteReview, stream);
  await c.startReview();
  await flushReview();
  assert.equal(calls, 2);
  assert.equal(c.review.loading, false);
  assert.equal(c.review.error, '');
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.changes[0].number, 1);
  unmount();
});

function validReviewStream(counter) {
  return async (_payload, { onEvent }) => {
    counter.calls += 1;
    onEvent({ type: 'meta', provider: 'anthropic', model: 'x' });
    onEvent({ type: 'delta', text: JSON.stringify({ changes: [
      { id: 1, cat: 'fix', anchor: 'Original', revised: 'Ursprung', reason: 'r' },
    ] }) });
  };
}

test('hiding the panel keeps suggestions and decisions when the text is unchanged', async () => {
  const counter = { calls: 0 };
  const { controller: c, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  await flushReview();
  assert.equal(counter.calls, 1);
  assert.equal(c.review.changes.length, 1);
  c.rejectChange(1);       // Entscheidung des Nutzers: ablehnen
  c.toggleReview();        // Panel ausblenden (Kopf-Button)
  assert.equal(c.review.open, false);
  await c.startReview();   // wieder einblenden
  await flushReview();
  assert.equal(counter.calls, 1, 'kein erneuter KI-Aufruf bei unverändertem Text');
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.status[1], 'rejected', 'frühere Entscheidung bleibt erhalten');
  unmount();
});

test('editing the note after hiding drops the cache and re-runs the review', async () => {
  const counter = { calls: 0 };
  const { controller: c, editor, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  await flushReview();
  assert.equal(counter.calls, 1);
  c.toggleReview(); // ausblenden (Cache gesichert)
  editor.value.chain().insertContentAt(1, { type: 'text', text: 'X' }).run(); // Text ändern
  await c.startReview();
  await flushReview();
  assert.equal(counter.calls, 2, 'nach Textänderung wird neu geprüft');
  unmount();
});

test('Verwerfen discards the cache so re-opening runs a fresh review', async () => {
  const counter = { calls: 0 };
  const { controller: c, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  await flushReview();
  c.discardReview(); // Verwerfen
  await c.startReview();
  await flushReview();
  assert.equal(counter.calls, 2, 'Verwerfen behält keine Vorschläge');
  unmount();
});

test('accepting a suggestion applies it immediately and removes the card', async () => {
  const counter = { calls: 0 };
  const { controller: c, editor, checkpoints, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  await flushReview();
  assert.equal(c.review.changes.length, 1);
  c.acceptChange(1);
  assert.equal(editor.value.getText().includes('Ursprung'), true, 'Verbesserung direkt umgesetzt');
  assert.equal(editor.value.getText().includes('Original'), false);
  assert.equal(c.review.changes.length, 0, 'angenommene Karte verschwindet');
  assert.deepEqual(checkpoints, ['ai']);
  unmount();
});

test('rejecting moves a suggestion to the rejected filter and keeps it', async () => {
  const counter = { calls: 0 };
  const { controller: c, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  await flushReview();
  c.rejectChange(1);
  assert.equal(c.review.status[1], 'rejected');
  assert.equal(c.openCount.value, 0);
  assert.equal(c.rejectedCount.value, 1);
  // Standardfilter 'open' zeigt die abgelehnte nicht; Filter 'rejected' schon.
  assert.equal(c.reviewCards.value.length, 0);
  c.setFilter('rejected');
  assert.equal(c.reviewCards.value.length, 1);
  c.reopenChange(1);
  assert.equal(c.review.status[1], 'open');
  unmount();
});

for (const dismiss of ['close', 'overlay']) {
  test(`${dismiss} preserves suggestions through repeated dismissal and restores the view`, async () => {
    const counter = { calls: 0 };
    const { controller: c, overlays, unmount } = setup(useNoteReview, validReviewStream(counter));
    await c.startReview();
    c.rejectChange(1);
    c.setFilter('rejected');
    c.review.instruction = 'Bitte kurz halten';
    if (dismiss === 'close') c.closeReview();
    else overlays.open('writing');
    assert.equal(c.review.open, false);
    overlays.closeAll();
    await c.startReview();
    assert.equal(counter.calls, 1);
    assert.equal(c.reviewCards.value.length, 1);
    assert.equal(c.review.status[1], 'rejected');
    assert.equal(c.review.filter, 'rejected');
    assert.equal(c.review.instruction, 'Bitte kurz halten');
    assert.equal(c.review.model, 'x');
    unmount();
  });
}

test('switching notes clears hidden suggestions even with identical text', async () => {
  const counter = { calls: 0 };
  const { controller: c, props, unmount } = setup(useNoteReview, validReviewStream(counter));
  await c.startReview();
  c.closeReview();
  props.noteId = 'two';
  await nextTick();
  await c.startReview();
  assert.equal(counter.calls, 2);
  unmount();
});

test('a selected suggestion can be deselected by clicking again or explicitly clearing focus', async () => {
  const { controller: c, unmount } = setup(useNoteReview, validReviewStream({ calls: 0 }));
  await c.startReview();
  c.revealChange(1);
  assert.equal(c.effectiveFocusId.value, 1);
  c.revealChange(1);
  assert.equal(c.effectiveFocusId.value, null);
  c.revealChange(1);
  c.clearFocus();
  assert.equal(c.effectiveFocusId.value, null);
  assert.equal(c.focusChange.value, null);
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.status[1], 'open');
  unmount();
});

test('review view preferences survive dismissal, note switches, and remounting', async () => {
  const values = new Map();
  const getStorage = () => ({ getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) });
  const stream = validReviewStream({ calls: 0 });
  const first = setup(useNoteReview, stream, { getStorage });
  const c = first.controller;
  await c.startReview();
  c.setSort('type');
  c.setFilter('rejected');
  c.discardReview();
  first.props.noteId = 'two';
  await nextTick();
  await c.startReview();
  assert.equal(c.review.sort, 'type');
  assert.equal(c.review.filter, 'rejected');
  c.acceptChange(1);
  assert.equal(c.review.filter, 'rejected', 'an empty filter must not replace the preference');
  first.unmount();
  const second = setup(useNoteReview, stream, { getStorage });
  assert.equal(second.controller.review.sort, 'type');
  assert.equal(second.controller.review.filter, 'rejected');
  second.unmount();
});

test('review view preferences tolerate invalid or unavailable storage', () => {
  for (const raw of ['null', '{', '{"sort":"bad","filter":"bad"}']) {
    const { controller: c, unmount } = setup(useNoteReview, validReviewStream({ calls: 0 }), {
      getStorage: () => ({ getItem: () => raw, setItem: () => { throw new Error('blocked'); } }),
    });
    assert.equal(c.review.sort, 'order');
    assert.equal(c.review.filter, 'open');
    assert.doesNotThrow(() => { c.setSort('type'); c.setFilter('all'); });
    c.setSort('invalid');
    c.setFilter('invalid');
    assert.equal(c.review.sort, 'type');
    assert.equal(c.review.filter, 'all');
    unmount();
  }
});

test('an incomplete review retries once with a compact request and never applies partial output', async () => {
  const payloads = [];
  const { controller: c, editor, unmount } = setup(useNoteReview, async (payload, { onEvent }) => {
    payloads.push(payload);
    if (!payload.retry) {
      onEvent({ type: 'delta', text: '{"changes":[' });
      throw Object.assign(new Error('Abgeschnitten'), { code: 'review_incomplete' });
    }
    await validReviewStream({ calls: 0 })(payload, { onEvent });
  });
  await c.startReview();
  await flushReview();
  assert.deepEqual(payloads.map(p => p.retry), [false, true]);
  assert.equal(c.review.loading, false);
  assert.equal(c.review.error, '');
  assert.equal(c.review.changes.length, 1);
  assert.equal(editor.value.getText(), 'Original text');
  unmount();
});

test('repeated incomplete review ends with an error after the single retry', async () => {
  let calls = 0;
  const { controller: c, unmount } = setup(useNoteReview, async () => {
    calls += 1;
    throw Object.assign(new Error('Abgeschnitten'), { code: 'review_incomplete' });
  });
  await c.startReview();
  await flushReview();
  assert.equal(calls, 2);
  assert.equal(c.review.loading, false);
  assert.equal(c.review.error, 'Abgeschnitten');
  unmount();
});

test('closing during the compact retry ignores late results', async () => {
  const pending = deferredStream();
  let calls = 0;
  const { controller: c, unmount } = setup(useNoteReview, (payload, options) => {
    calls += 1;
    if (calls === 1) return Promise.reject(Object.assign(new Error('Abgeschnitten'), { code: 'review_incomplete' }));
    return pending.stream(payload, options);
  });
  await c.startReview();
  assert.equal(calls, 2);
  c.closeReview();
  assert.equal(pending.calls[0].signal.aborted, true);
  pending.calls[0].onEvent({ type: 'delta', text: '{"changes":[]}' });
  pending.calls[0].resolve();
  await flushReview();
  assert.equal(c.review.open, false);
  assert.equal(c.review.loading, false);
  assert.equal(c.review.preview, '');
  assert.deepEqual(c.review.changes, []);
  unmount();
});

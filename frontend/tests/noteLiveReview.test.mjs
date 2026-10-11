import assert from 'node:assert/strict';
import test from 'node:test';
import { reactive, shallowRef } from 'vue';
import { useNoteReview } from '../src/components/notes/composables/useNoteReview.js';
import { liveReviewScope } from '../src/components/notes/composables/noteLiveReview.js';
import { createNoteOverlayCoordinator } from '../src/components/notes/composables/noteOverlayCoordinator.js';
import { createTestEditor, mountController } from './helpers/noteEditorHarness.mjs';

const paragraph = text => ({ type: 'paragraph', content: [{ type: 'text', text }] });
const fix = (anchor = 'Fehler', revised = 'Korrektur') => ({ id: 1, cat: 'fix', anchor, revised, summary: 'Schreibweise korrigieren.' });
const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };
function setup(t, stream, content = null) {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  let elapsed = 0;
  const advance = t.mock.timers.tick.bind(t.mock.timers);
  t.mock.timers.tick = ms => { elapsed += ms; advance(ms); };
  const ed = createTestEditor('Fehler im Satz.', content);
  const listeners = new Set();
  ed.on = (event, fn) => { if (event === 'transaction') listeners.add(fn); };
  ed.off = (event, fn) => { if (event === 'transaction') listeners.delete(fn); };
  const dispatch = ed.view.dispatch;
  ed.view.dispatch = tr => { dispatch(tr); for (const fn of listeners) fn({ transaction: tr }); };
  const editor = shallowRef(ed);
  const props = reactive({ noteId: 'one', aiAvailable: true });
  const mounted = mountController(() => useNoteReview({ editor, props, stream,
    overlays: createNoteOverlayCoordinator(), onCheckpoint() {}, getStorage: () => null, now: () => elapsed }));
  t.after(mounted.unmount);
  return { c: mounted.controller, ed, editor, props };
}
function responding(changes, calls) {
  return async (payload, { onEvent }) => { calls.push(payload); onEvent({ type: 'delta', text: JSON.stringify({ changes }) }); };
}

test('typing batches requests at least 15 seconds apart, keeps valid cards and stable IDs, and never moves the caret', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix()], calls));
  await c.startReview();
  const id = c.review.changes[0].id;
  ed.view.dispatch(ed.state.tr.insertText(' Mehr', ed.state.doc.content.size - 1));
  assert.equal(c.review.changes[0].id, id);
  t.mock.timers.tick(1000);
  ed.view.dispatch(ed.state.tr.insertText(' Text', ed.state.doc.content.size - 1));
  const selection = ed.state.selection;
  t.mock.timers.tick(13999);
  assert.equal(calls.length, 1);
  t.mock.timers.tick(1);
  await flush();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].mode, 'live');
  assert.equal(c.review.changes[0].id, id);
  assert.equal(c.review.stale, false);
  assert.equal(ed.state.selection.from, selection.from);
});

test('ignored hints remain ignored across edits elsewhere and a full check', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix()], calls));
  await c.startReview();
  c.rejectChange(1);
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(c.review.status[1], 'rejected');
  assert.equal(c.openCount.value, 0);
  c.reviewWholeNote();
  await flush();
  assert.equal(calls.at(-1).mode, 'full');
  assert.equal(c.review.status[1], 'rejected');
  ed.view.dispatch(ed.state.tr.insertText('X', 3));
  assert.equal(c.review.changes.length, 0);
});

test('typing lets the local request finish and never starts overlapping automatic checks', async t => {
  const calls = [];
  const { c, ed } = setup(t, (payload, options) => new Promise(resolve => calls.push({ payload, ...options, resolve })));
  const first = c.startReview();
  calls[0].onEvent({ type: 'delta', text: JSON.stringify({ changes: [fix()] }) });
  calls[0].resolve();
  await first;
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  t.mock.timers.tick(15000);
  assert.equal(c.review.loading, true);
  assert.equal(c.review.changes.length, 1);
  ed.view.dispatch(ed.state.tr.insertText(' Noch', ed.state.doc.content.size - 1));
  assert.equal(calls[1].signal.aborted, false);
  t.mock.timers.tick(15000);
  assert.equal(calls.length, 2, 'no overlapping local generation while typing');
  calls[1].onEvent({ type: 'delta', text: JSON.stringify({ changes: [] }) });
  calls[1].resolve();
  await flush();
  assert.equal(c.review.loading, false);
  assert.equal(c.review.changes.length, 1, 'outdated result does not replace existing cards');
  t.mock.timers.tick(2999);
  assert.equal(calls.length, 2);
  t.mock.timers.tick(1);
  assert.equal(calls.length, 3);
  calls[2].onEvent({ type: 'delta', text: JSON.stringify({ changes: [fix()] }) });
  calls[2].resolve();
  await flush();
  assert.equal(c.review.loading, false);
  assert.equal(c.review.changes[0].id, 1);
});

test('pause, close, note switch and unavailable AI stop automatic checks', async t => {
  const calls = [];
  const { c, ed, props } = setup(t, responding([fix()], calls));
  await c.startReview();
  c.togglePause();
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  t.mock.timers.tick(2000);
  assert.equal(calls.length, 1);
  c.togglePause();
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(calls.length, 2);
  ed.view.dispatch(ed.state.tr.insertText(' Mehr', ed.state.doc.content.size - 1));
  c.closeReview();
  t.mock.timers.tick(2000);
  assert.equal(calls.length, 2);
  await c.startReview();
  ed.view.dispatch(ed.state.tr.insertText(' Extra', ed.state.doc.content.size - 1));
  props.aiAvailable = false;
  t.mock.timers.tick(2000);
  assert.equal(calls.length, 2);
  props.aiAvailable = true;
  props.noteId = 'two';
  t.mock.timers.tick(2000);
  assert.equal(calls.length, 2);
  assert.equal(c.review.open, false);
});

test('empty notes activate the live mode and check the first text after a pause', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix()], calls), { type: 'doc', content: [{ type: 'paragraph' }] });
  await c.startReview();
  assert.equal(c.review.open, true);
  assert.equal(c.review.error, '');
  assert.equal(calls.length, 0);
  ed.view.dispatch(ed.state.tr.insertText('Fehler', 1));
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(calls.length, 1);
  assert.equal(c.review.changes.length, 1);
});

test('live mode drops additions; the full check retains them and sends instructions', async t => {
  const calls = [];
  const addition = { id: 2, cat: 'add', anchor: 'Satz', revised: 'Mehr Inhalt', confidence: 'niedrig' };
  const { c } = setup(t, responding([fix(), addition], calls));
  await c.startReview();
  assert.equal(c.review.changes.length, 1);
  assert.equal(calls[0].extra_instruction, '');
  c.review.instruction = 'Zusammenhänge prüfen';
  c.reviewWholeNote();
  await flush();
  assert.equal(c.review.changes.length, 2);
  assert.equal(calls.at(-1).extra_instruction, 'Zusammenhänge prüfen');
});

test('accepting during a check cancels it, writes a single undoable change and resumes checking', async t => {
  const calls = [];
  const { c, ed } = setup(t, (payload, options) => new Promise(resolve => calls.push({ payload, ...options, resolve })));
  const first = c.startReview();
  calls[0].onEvent({ type: 'delta', text: JSON.stringify({ changes: [fix()] }) });
  calls[0].resolve();
  await first;
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  t.mock.timers.tick(15000);
  const before = ed.getText();
  c.acceptChange(1);
  assert.equal(calls[1].signal.aborted, true);
  assert.equal(ed.getText(), before.replace('Fehler', 'Korrektur'));
  calls[1].onEvent({ type: 'delta', text: JSON.stringify({ changes: [fix()] }) });
  calls[1].resolve();
  await flush();
  assert.equal(c.review.changes.length, 0);
  ed.commands.undo();
  assert.equal(ed.getText(), before);
  t.mock.timers.tick(15000);
  assert.equal(calls.length, 3);
});

test('large notes and single long paragraphs are checked in bounded excerpts until complete', async t => {
  const calls = [];
  const { c } = setup(t, responding([], calls), { type: 'doc', content: [paragraph('lang '.repeat(3000)), paragraph('Ende.')] });
  await c.startReview();
  for (let i = 0; i < 12 && c.review.pending; i++) { t.mock.timers.tick(15000); await flush(); }
  assert.ok(calls.length >= 4);
  assert.ok(calls.every(call => call.note_text.length <= 2000));
  assert.ok(calls.at(-1).note_text.endsWith('Ende.'));
  assert.equal(c.review.pending, false);
  assert.equal(c.review.stale, false);
});

test('scope skips checked nodes, includes neighboring context and maps back into the document', () => {
  const ed = createTestEditor('', { type: 'doc', content: ['A'.repeat(3000), 'B'.repeat(3000), 'Fehler', 'Nachbar', 'C'.repeat(3000)].map(paragraph) });
  const checked = new WeakMap();
  ed.state.doc.forEach(node => checked.set(node, node.textContent.length));
  checked.delete(ed.state.doc.child(2));
  const scope = liveReviewScope(ed.state.doc, checked);
  assert.ok(scope.text.includes('Fehler\nNachbar'));
  assert.ok(!scope.text.includes('A'));
  assert.equal(scope.structure.find(block => block.text === 'Fehler').id, 'b3');
  const start = scope.text.indexOf('Fehler');
  assert.equal(ed.state.doc.textBetween(scope.map[start], scope.map[start + 5] + 1), 'Fehler');
});

test('accept and hide preserve decisions on the correct occurrence of duplicate words', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix('Fehler', 'Korrektur'), fix('Fehler', 'Verbesserung')], calls),
    { type: 'doc', content: [paragraph('Fehler zuerst, Fehler danach.')] });
  await c.startReview();
  c.rejectChange(2);
  c.acceptChange(1);
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.changes[0].anchor, 'Fehler');
  assert.equal(ed.state.doc.textBetween(c.review.changes[0].from, c.review.changes[0].to), 'Fehler');
  assert.equal(c.review.status[2], 'rejected');
  c.closeReview();
  await c.startReview();
  assert.equal(c.review.status[2], 'rejected');
  assert.equal(ed.state.doc.textBetween(c.review.changes[0].from, c.review.changes[0].to), 'Fehler');
});

test('whitespace-only blocks and long leading whitespace cannot stall the live check', async t => {
  const calls = [];
  const { c } = setup(t, responding([fix()], calls), { type: 'doc', content: [paragraph(' '.repeat(6000)), paragraph(' '.repeat(6000) + 'Fehler')] });
  await c.startReview();
  assert.equal(calls.length, 1);
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.error, '');
  assert.equal(c.review.stale, false);
});

test('deleting a whole structural target removes the suggestion safely', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([{ id: 1, cat: 'format', block_ids: ['b1'], anchor: 'Fehler', revised: '## Fehler' }], calls),
    { type: 'doc', content: [paragraph('Fehler'), paragraph('Danach')] });
  await c.startReview();
  ed.view.dispatch(ed.state.tr.delete(0, ed.state.doc.firstChild.nodeSize));
  assert.equal(c.review.changes.length, 0);
  assert.equal(ed.getText(), 'Danach');
});

test('undoing an accepted structural change rechecks a previously checked node', async t => {
  const calls = [];
  const original = paragraph('Fehler');
  const { c, ed } = setup(t, responding([{ id: 1, cat: 'format', block_ids: ['b1'], anchor: 'Fehler', revised: '## Fehler' }], calls),
    { type: 'doc', content: [original] });
  await c.startReview();
  c.acceptChange(1);
  ed.commands.undo();
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(calls.length, 2);
  assert.equal(c.review.changes.length, 1);
});

test('a recent edit extends the writing pause even when the 15 second interval has elapsed', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix()], calls));
  await c.startReview();
  t.mock.timers.tick(14000);
  ed.view.dispatch(ed.state.tr.insertText('X', ed.state.doc.content.size - 1));
  t.mock.timers.tick(2999);
  assert.equal(calls.length, 1);
  t.mock.timers.tick(1);
  await flush();
  assert.equal(calls.length, 2);
  t.mock.timers.tick(100000);
  assert.equal(calls.length, 2, 'unchanged notes never cause background polling');
});

test('local reviews work with cloud writing unavailable and pause when local AI becomes unavailable', async t => {
  const calls = [];
  const { c, props, ed } = setup(t, responding([fix()], calls));
  props.aiAvailable = false;
  props.reviewAvailable = true;
  await c.startReview();
  assert.equal(calls.length, 1);
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  props.reviewAvailable = false;
  t.mock.timers.tick(15000);
  assert.equal(calls.length, 1);
});

test('invalid live output fails once and preserves hints instead of starting another generation', async t => {
  const calls = [];
  const { c, ed } = setup(t, async (payload, { onEvent }) => {
    calls.push(payload);
    onEvent({ type: 'delta', text: calls.length === 1 ? JSON.stringify({ changes: [fix()] }) : '{"changes":[' });
  });
  await c.startReview();
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(calls.length, 2);
  assert.equal(c.review.changes.length, 1);
  assert.ok(c.review.error);
  assert.equal(c.review.pending, false);
});

test('an invented model anchor cannot interrupt live checking or discard valid hints', async t => {
  const calls = [];
  const { c, ed } = setup(t, async (payload, { onEvent }) => {
    calls.push(payload);
    onEvent({ type: 'delta', text: JSON.stringify({ changes: calls.length === 1 ? [fix()] : [fix('Ergebniss', 'Ergebnis')] }) });
  });
  await c.startReview();
  ed.view.dispatch(ed.state.tr.insertText(' Weiter', ed.state.doc.content.size - 1));
  const before = ed.state.doc.toJSON();
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(c.review.error, '');
  assert.match(c.review.notice, /unsicherer KI-Hinweis/);
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.changes[0].anchor, 'Fehler');
  assert.equal(c.review.stale, false);
  assert.deepEqual(ed.state.doc.toJSON(), before);
  ed.view.dispatch(ed.state.tr.insertText(' Neuer Satz.', ed.state.doc.content.size - 1));
  t.mock.timers.tick(15000);
  await flush();
  assert.equal(calls.length, 3, 'automatic checks continue on further edits');
});

test('safe hints remain usable alongside unmappable model suggestions', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([fix('Ergebniss', 'Ergebnis'), fix()], calls));
  await c.startReview();
  assert.equal(c.review.error, '');
  assert.match(c.review.notice, /ausgelassen/);
  assert.equal(c.review.changes.length, 1);
  c.acceptChange(c.review.changes[0].id);
  assert.equal(ed.getText(), 'Korrektur im Satz.');
});

test('live formatting cannot append a neighboring sentence to an otherwise valid anchor', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([{ id: 1, cat: 'format', anchor: 'Ein Projekt wird einer Gruppe zugeordnet.',
    revised: 'Ein Projekt wird einer Gruppe zugeordnet. Bei fehlenden Kapazitäten wird es verschoben.',
    summary: 'Kurze Erklärung hinzugefügt.' }], calls), { type: 'doc', content: [paragraph('Ein Projekt wird einer Gruppe zugeordnet.'), paragraph('Bei fehlenden Kapazitäten wird es verschoben.')] });
  const original = ed.state.doc.toJSON();
  await c.startReview();
  assert.equal(c.review.error, '');
  assert.equal(c.review.changes.length, 0);
  assert.match(c.review.notice, /ausgelassen/);
  assert.deepEqual(ed.state.doc.toJSON(), original);
});

test('live formatting still supports headings, emphasis and simple lists without new text', async t => {
  const calls = [];
  const { c } = setup(t, responding([{ id: 1, cat: 'format', anchor: 'Name: Anna', revised: '**Name:** Anna' }], calls),
    { type: 'doc', content: [paragraph('Name: Anna')] });
  await c.startReview();
  assert.equal(c.review.changes.length, 1);
  assert.equal(c.review.notice, '');
});

test('an inline live correction cannot merge independent source blocks', async t => {
  const calls = [];
  const { c, ed } = setup(t, responding([{ id: 1, cat: 'fix', anchor: 'Erste Aufgabe\nZweite Aufgabe',
    revised: 'Erste und zweite Aufgabe', summary: 'Aufgaben zusammenfassen.' }], calls),
    { type: 'doc', content: [paragraph('Erste Aufgabe'), paragraph('Zweite Aufgabe')] });
  await c.startReview();
  assert.equal(c.review.error, '');
  assert.equal(c.review.changes.length, 0);
  assert.match(c.review.notice, /ausgelassen/);
  assert.equal(ed.state.doc.childCount, 2);
});

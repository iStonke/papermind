import test from 'node:test';
import assert from 'node:assert/strict';
import { nextTick, ref } from 'vue';
import { useRecordAutosave } from '../src/composables/useRecordAutosave.js';

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};

function editor(persist) {
  const items = ref([{ id: 'a', name: 'Alpha' }, { id: 'b', name: 'Beta' }]);
  const state = useRecordAutosave({ items: () => items.value, delay: 60_000,
    readDraft: item => ({ name: item.name }), toPayload: draft => ({ name: draft.name.trim() }),
    validate: draft => draft.name.trim().length >= 2, persist });
  state.select(items.value[0]);
  return { state, items, name: state.field('name') };
}

test('switching records flushes the old draft to its original ID', async () => {
  const calls = [];
  const { state, items, name } = editor(async (id, payload) => { calls.push({ id, ...payload }); return payload; });
  name.value = 'Alpha neu';
  state.select(items.value[1]);
  name.value = 'Beta neu';
  await state.flush();
  assert.deepEqual(calls, [{ id: 'a', name: 'Alpha neu' }, { id: 'b', name: 'Beta neu' }]);
  assert.equal(name.value, 'Beta neu');
});

test('slow saves are serialized and acknowledge only the snapshot they sent', async () => {
  const first = deferred();
  const calls = [];
  const { state, name } = editor(async (id, payload) => {
    calls.push(payload.name);
    if (calls.length === 1) await first.promise;
    return payload;
  });
  name.value = 'Erster Stand';
  const saving = state.save();
  await nextTick();
  name.value = 'Neuster Stand';
  state.save();
  await nextTick();
  assert.deepEqual(calls, ['Erster Stand']);
  assert.equal(state.state.value, 'saving');
  first.resolve();
  await saving;
  await state.flush();
  assert.deepEqual(calls, ['Erster Stand', 'Neuster Stand']);
  assert.equal(name.value, 'Neuster Stand');
  assert.equal(state.state.value, 'saved');
});

test('reverting during an in-flight save restores the original persisted value', async () => {
  const first = deferred();
  const calls = [];
  const { state, name } = editor(async (id, payload) => {
    calls.push(payload.name);
    if (calls.length === 1) await first.promise;
    return payload;
  });
  name.value = 'Änderung';
  const saving = state.save();
  await nextTick();
  name.value = 'Alpha';
  first.resolve();
  await saving;
  await state.flush();
  assert.deepEqual(calls, ['Änderung', 'Alpha']);
});

test('failed and invalid drafts survive reloads and selection changes and can be retried', async () => {
  let fail = true;
  const { state, items, name } = editor(async (id, payload) => {
    if (fail) throw new Error('Offline');
    return payload;
  });
  name.value = 'Entwurf';
  assert.equal(await state.save(), false);
  assert.equal(state.state.value, 'error');
  items.value = [...items.value];
  await nextTick();
  assert.equal(name.value, 'Entwurf');
  state.select(items.value[1]);
  await state.flush();
  state.select(items.value[0]);
  assert.equal(name.value, 'Entwurf');
  fail = false;
  assert.equal(await state.save(), true);
  name.value = '';
  assert.equal(await state.save(), false);
  items.value = [...items.value];
  await nextTick();
  assert.equal(name.value, '');
  assert.equal(state.state.value, 'invalid');
  name.value = 'Gültig';
  await state.flush();
});

test('closing an editor flushes immediately instead of dropping a debounce', async () => {
  const calls = [];
  const { state, name } = editor(async (id, payload) => { calls.push(payload); return payload; });
  name.value = 'Vor dem Schließen';
  state.select(null);
  await state.flush();
  assert.deepEqual(calls, [{ name: 'Vor dem Schließen' }]);
  assert.equal(state.selectedId.value, null);
});

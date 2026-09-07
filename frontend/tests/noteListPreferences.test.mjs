import test from 'node:test';
import assert from 'node:assert/strict';
import { ref, nextTick } from 'vue';
import { mountController } from './helpers/noteEditorHarness.mjs';
import { useNoteListPreferences } from '../src/components/notes/composables/useNoteListPreferences.js';

function storage(initial = null) {
  let value = initial;
  return { getItem: () => value, setItem: (_, next) => { value = next; } };
}

test('sort, period and notebook survive remount and late account settings', async () => {
  const saved = storage();
  const defaultSort = ref('updated');
  const mount = () => mountController(() => useNoteListPreferences(() => defaultSort.value, () => saved));
  const first = mount();
  first.controller.sortMode.value = 'created';
  first.controller.dateRange.value = 'last_7_days';
  first.controller.notebookFilter.value = 'notebook-123';
  first.unmount();
  const second = mount();
  defaultSort.value = 'title';
  await nextTick();
  assert.equal(second.controller.sortMode.value, 'created');
  assert.equal(second.controller.dateRange.value, 'last_7_days');
  assert.equal(second.controller.notebookFilter.value, 'notebook-123');
  second.controller.dateRange.value = '';
  second.controller.notebookFilter.value = '';
  second.unmount();
  const third = mount();
  assert.equal(third.controller.dateRange.value, '');
  assert.equal(third.controller.notebookFilter.value, '');
  third.unmount();
});

test('missing preferences follow asynchronously loaded default sort', async () => {
  const defaultSort = ref('updated');
  const mounted = mountController(() => useNoteListPreferences(() => defaultSort.value, () => storage()));
  defaultSort.value = 'title';
  await nextTick();
  assert.equal(mounted.controller.sortMode.value, 'title');
  mounted.unmount();
});

for (const raw of ['{bad', 'null', '{"sortMode":"wrong","dateRange":"wrong","notebookFilter":12}']) {
  test(`invalid stored preferences fall back safely: ${raw}`, () => {
    const mounted = mountController(() => useNoteListPreferences(() => 'created', () => storage(raw)));
    assert.equal(mounted.controller.sortMode.value, 'created');
    assert.equal(mounted.controller.dateRange.value, '');
    assert.equal(mounted.controller.notebookFilter.value, '');
    mounted.unmount();
  });
}

test('blocked storage does not prevent filter changes', () => {
  const mounted = mountController(() => useNoteListPreferences(() => 'updated', () => { throw new Error('blocked'); }));
  mounted.controller.notebookFilter.value = 'none';
  assert.equal(mounted.controller.notebookFilter.value, 'none');
  mounted.unmount();
});

test('management sort persists independently of compact list filters and late defaults', async () => {
  const values = new Map();
  const saved = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
  const defaultSort = ref('updated');
  const mount = key => mountController(() => useNoteListPreferences(() => defaultSort.value, () => saved, key));
  const list = mount(undefined);
  list.controller.sortMode.value = 'created';
  list.controller.dateRange.value = 'today';
  const management = mount('pm-notes-manage-preferences-v1');
  management.controller.sortMode.value = 'title';
  management.unmount();
  list.unmount();
  const restored = mount('pm-notes-manage-preferences-v1');
  defaultSort.value = 'created';
  await nextTick();
  assert.equal(restored.controller.sortMode.value, 'title');
  const restoredList = mount(undefined);
  assert.equal(restoredList.controller.sortMode.value, 'created');
  assert.equal(restoredList.controller.dateRange.value, 'today');
  restored.unmount();
  restoredList.unmount();
});

test('reverse sort survives a remount and older saved preferences default to normal order', () => {
  const saved = storage('{"sortMode":"title"}');
  const mount = () => mountController(() => useNoteListPreferences(() => 'updated', () => saved));
  const first = mount();
  assert.equal(first.controller.reverseSort.value, false);
  first.controller.reverseSort.value = true;
  first.unmount();
  const second = mount();
  assert.equal(second.controller.sortMode.value, 'title');
  assert.equal(second.controller.reverseSort.value, true);
  second.unmount();
});

test('grouping and period persist together with sorting', () => {
  const saved = storage();
  const mount = () => mountController(() => useNoteListPreferences(() => 'updated', () => saved));
  const first = mount();
  first.controller.grouping.value = 'notebook';
  first.controller.dateRange.value = 'last_30_days';
  first.controller.reverseSort.value = true;
  first.unmount();
  const restored = mount();
  assert.equal(restored.controller.grouping.value, 'notebook');
  assert.equal(restored.controller.dateRange.value, 'last_30_days');
  assert.equal(restored.controller.reverseSort.value, true);
  restored.unmount();
});

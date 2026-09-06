import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { useNotifications } from '../src/stores/notifications.js';
import { notifyNoteDeleted } from '../src/utils/noteDeletionFeedback.js';
import { useNotesStore } from '../src/stores/notes.js';

const notifications = useNotifications();
function setup(t) {
  const timers = new Map();
  let nextId = 1;
  const previousWindow = globalThis.window;
  globalThis.window = {
    setTimeout(fn, delay) { const id = nextId++; timers.set(id, { fn, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  t.after(() => { notifications.clearAllNotifications(); globalThis.window = previousWindow; });
  return timers;
}

test('deletion uses the standard five-second notification and expires', (t) => {
  const timers = setup(t);
  notifyNoteDeleted({ id: 'a', title: 'Einkauf' }, { restore: async () => {} });
  const toast = notifications.visibleNotifications.value[0];
  assert.equal(toast.title, 'Notiz gelöscht');
  assert.equal(toast.action.label, 'Rückgängig');
  const timer = [...timers.values()][0];
  assert.equal(timer.delay, 5000);
  timer.fn();
  assert.equal(notifications.visibleNotifications.value.length, 0);
});

test('same-title deletions retain independent undo actions and block double clicks', async (t) => {
  const timers = setup(t);
  let finish;
  const calls = [];
  const restore = (id) => { calls.push(id); return new Promise((resolve) => { finish = resolve; }); };
  const first = notifyNoteDeleted({ id: 'a', title: '' }, { restore });
  notifyNoteDeleted({ id: 'b', title: '' }, { restore });
  assert.equal(notifications.visibleNotifications.value.length, 2);
  const pending = notifications.executeNotificationAction(first);
  await notifications.executeNotificationAction(first);
  assert.deepEqual(calls, ['a']);
  assert.equal(timers.size, 1);
  finish();
  await pending;
  assert.equal(notifications.visibleNotifications.value.length, 1);
});

test('failed restoration offers retry and independent hover/focus pauses work', async (t) => {
  const timers = setup(t);
  let attempts = 0;
  const id = notifyNoteDeleted({ id: 'retry', title: 'Retry' }, {
    restore: async () => { if (++attempts === 1) throw new Error('Failed to fetch'); },
  });
  notifications.pauseNotificationTimer(id, 'hover');
  notifications.pauseNotificationTimer(id, 'focus');
  notifications.resumeNotificationTimer(id, 'hover');
  assert.equal(timers.size, 0);
  await notifications.executeNotificationAction(id);
  assert.equal(notifications.visibleNotifications.value[0].actionRunning, false);
  assert.equal(notifications.visibleNotifications.value[1].type, 'error');
  notifications.resumeNotificationTimer(id, 'focus');
  assert.ok([...timers.values()].some((timer) => timer.delay === 5000));
  await notifications.executeNotificationAction(id);
  assert.equal(attempts, 2);
  assert.ok(!notifications.visibleNotifications.value.some((item) => item.id === id));
});

test('queued deletion starts its full timeout only when displayed', (t) => {
  const timers = setup(t);
  const ids = ['one', 'two', 'three'].map((id) => notifyNoteDeleted({ id }, { restore: async () => {} }));
  assert.equal(timers.size, 2);
  assert.equal(notifications.queuedNotifications.value.length, 1);
  notifications.dismissNotification(ids[0]);
  assert.equal(notifications.visibleNotifications.value[1].id, ids[2]);
  assert.equal([...timers.values()].at(-1).delay, 5000);
});

test('undo restores the complete note, preview and metadata without duplicate list entries', async (t) => {
  setup(t);
  setActivePinia(createPinia());
  const store = useNotesStore();
  const restored = { id: 'saved', title: 'Test', notebook_id: 'book', is_pinned: true,
    updated_at: '2026-09-06T10:00:00Z', body_json: { type: 'doc', content: [
      { type: 'paragraph', content: [{ type: 'text', text: 'Inhalt' }] },
    ] } };
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.match(String(url), /\/api\/notes\/saved\/restore$/);
    assert.equal(options.method, 'POST');
    return new Response(JSON.stringify(restored), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  let refreshed = 0;
  const id = notifyNoteDeleted(restored, { restore: store.restore, onRestored: () => refreshed++ });
  await notifications.executeNotificationAction(id);
  assert.equal(refreshed, 1);
  assert.equal(store.notes[0].preview, 'Inhalt');
  assert.equal(store.notes[0].notebook_id, 'book');
  assert.equal(store.notes[0].is_pinned, true);
  assert.deepEqual(store.peek('saved').body_json, restored.body_json);
  await store.restore('saved');
  assert.equal(store.notes.length, 1);
});

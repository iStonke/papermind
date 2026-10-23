import { effectScope, ref, watch } from 'vue';
import { apiFetch } from '../api/client.js';
import { apiSessionGeneration, onApiSessionReset } from '../api/session.js';
import { discardImportInboxItems } from '../api/importInbox.js';
import { useNotifications } from '../stores/notifications.js';
import { scannerDraft } from '../utils/importScanDraft.js';

const controllers = new WeakMap();
export const AVAILABLE_REMOVAL_UNDO_MS = 10000;
const sources = draft => new Set((draft?.documents || []).flatMap(doc => doc.pages.map(page => page.sourceFileId)));
function count(draft, items) {
  const seen = sources(draft);
  return (draft?.documents || []).reduce((sum, doc) => sum + doc.pages.length, 0) + items.reduce((sum, item) => {
    if (seen.has(item.source_file_id)) return sum;
    seen.add(item.source_file_id);
    return sum + Number(item.page_count || 0);
  }, 0);
}

export function mergeAvailableDrafts(older, newer) {
  if (!older) return newer;
  if (!newer) return older;
  return { ...older, ...newer,
    documents: [...new Map([...older.documents, ...newer.documents].map(doc => [doc.id, doc])).values()],
    sourceMeta: [...new Map([...older.sourceMeta, ...newer.sourceMeta])],
    files: [...new Map([...(older.files || []), ...(newer.files || [])])],
    pendingCommit: newer.pendingCommit || older.pendingCommit || null,
  };
}

// One session-owned controller survives closing the dialog and navigating away.
// Reloads reconstruct its timers and undo data from the durable draft journal.
export function useAvailableImportRemoval(store, options) {
  let controller = controllers.get(store);
  if (controller) { controller.attach(options); return controller; }
  const generation = apiSessionGeneration(), scope = effectScope(true);
  const { notify, dismissNotification } = useNotifications();
  const busy = ref(false), blocked = ref(false), timers = new Map(), notices = new Map(), running = new Set();
  let bindings = options, disposed = false;
  const current = () => !disposed && generation === apiSessionGeneration();
  const find = id => store.availableRemovals.find(entry => entry.id === id);
  const save = () => bindings.save();
  function clear(id) {
    clearTimeout(timers.get(id)); timers.delete(id);
    dismissNotification(notices.get(id)); notices.delete(id);
  }
  function restore(entry) {
    store.$patch(state => {
      state.availableDraft = mergeAvailableDrafts(entry.draft, state.availableDraft);
      state.availableRemovals = state.availableRemovals.filter(item => item.id !== entry.id);
    });
  }
  function haltRemovals() {
    if (!current()) return;
    blocked.value = true;
    // A failed durable write must leave every queued snapshot accessible.
    for (const entry of [...store.availableRemovals]) {
      clear(entry.id);
      restore(entry);
    }
  }
  async function undo(id) {
    const entry = find(id);
    if (!current() || !entry || running.has(id) || Date.now() > entry.expiresAt) return;
    clear(id);
    restore(entry);
    // On a storage failure retain the recovered pages in memory and stop all
    // destructive work. The existing persistence warning asks to keep it open.
    if (!await save()) haltRemovals();
  }
  async function finalize(id) {
    const entry = find(id);
    if (!current() || blocked.value || !entry || running.has(id)) return;
    if (Date.now() < entry.expiresAt) return schedule(entry);
    running.add(id); clear(id);
    const completed = new Set();
    const protectedSources = new Set();
    let failure;
    try {
      // A revision-checked write must succeed before any server mutation.
      if (!await save()) { haltRemovals(); return; }
      if (!current()) return;
      for (const sourceId of [...store.collectUsedSourceFileIds(), ...sources(store.availableDraft)]) protectedSources.add(sourceId);
      const items = entry.items.filter(item => !protectedSources.has(item.source_file_id));
      if (items.length) {
        await discardImportInboxItems([...new Set(items.map(item => item.id))]);
        if (!current()) return;
        for (const item of items) completed.add(item.source_file_id);
      }
      const inboxSources = new Set(entry.items.map(item => item.source_file_id));
      for (const sourceId of sources(entry.draft)) {
        if (protectedSources.has(sourceId) || inboxSources.has(sourceId)) continue;
        try { await apiFetch(`/api/import/source/${encodeURIComponent(sourceId)}`, { method: 'DELETE' }); }
        catch (error) { if (error.status !== 404) throw error; }
        if (!current()) return;
        completed.add(sourceId);
      }
    } catch (error) { failure = error; }
    finally { running.delete(id); }
    if (!current()) return;
    bindings.finalized?.({ sourceFileIds: [...completed], itemIds: entry.items.filter(item => completed.has(item.source_file_id)).map(item => item.id) });
    if (failure) {
      const keep = sourceId => !completed.has(sourceId) && !protectedSources.has(sourceId);
      const documents = (entry.draft?.documents || []).map(doc => ({ ...doc, pages: doc.pages.filter(page => keep(page.sourceFileId)) })).filter(doc => doc.pages.length);
      const keptSources = new Set(documents.flatMap(doc => doc.pages.map(page => page.sourceFileId)));
      const draft = documents.length ? { ...entry.draft, documents,
        sourceMeta: entry.draft.sourceMeta.filter(([id]) => keptSources.has(id)), files: (entry.draft.files || []).filter(([id]) => keptSources.has(id)) } : null;
      restore({ ...entry, draft });
      notify({ type: 'warning', message: 'Einige Seiten konnten nicht entfernt werden. Sie stehen wieder unter „Verfügbare Seiten“ bereit.' });
    } else store.availableRemovals = store.availableRemovals.filter(item => item.id !== id);
    await save();
  }
  function schedule(entry) {
    if (!current() || blocked.value || entry.ready === false || timers.has(entry.id) || running.has(entry.id)) return;
    const remaining = Math.max(0, entry.expiresAt - Date.now());
    if (remaining && !notices.has(entry.id)) {
      notices.set(entry.id, notify({ type: 'info', critical: true, priority: true, timeoutMs: remaining,
        message: `${entry.pageCount} ${entry.pageCount === 1 ? 'Seite entfernt.' : 'Seiten entfernt.'}`,
        action: { label: 'Rückgängig', onClick: () => undo(entry.id) },
      }));
    }
    // The action is dismissed at the same deadline, even if a toast is hovered.
    timers.set(entry.id, setTimeout(() => { timers.delete(entry.id); void finalize(entry.id); }, remaining));
  }
  async function remove() {
    if (busy.value || blocked.value || !current()) return;
    if (store.availableDraft?.pendingCommit) return;
    busy.value = true;
    try {
      const protectedSources = store.collectUsedSourceFileIds();
      const draft = scannerDraft(store.availableDraft);
      if ([...sources(draft)].some(id => protectedSources.has(id))) return;
      const items = new Map((bindings.items() || []).filter(item => !protectedSources.has(item.source_file_id)
        && !store.removedAvailableSources.has(item.source_file_id)).map(item => [item.id, { ...item }]));
      const pageCount = count(draft, [...items.values()]);
      if (!pageCount) return;
      for (const [sourceId, meta] of draft?.sourceMeta || []) if (meta.inboxItemId && !items.has(meta.inboxItemId)) {
        items.set(meta.inboxItemId, { id: meta.inboxItemId, source_file_id: sourceId, page_count: meta.pageCount || 0 });
      }
      const entry = { id: crypto.randomUUID(), expiresAt: Date.now() + AVAILABLE_REMOVAL_UNDO_MS,
        pageCount, draft, items: [...items.values()], ready: false };
      store.$patch(state => { state.availableDraft = null; state.availableRemovals.push(entry); });
      if (!await save()) { haltRemovals(); return; }
      if (current() && find(entry.id)) find(entry.id).ready = true;
    } finally { busy.value = false; }
  }
  scope.run(() => watch(() => store.availableRemovals.map(entry => `${entry.id}:${entry.expiresAt}:${entry.ready}`), () => {
    const ids = new Set(store.availableRemovals.map(entry => entry.id));
    for (const id of timers.keys()) if (!ids.has(id)) clear(id);
    for (const entry of store.availableRemovals) schedule(entry);
  }, { immediate: true }));
  const unsubscribe = onApiSessionReset(() => {
    disposed = true; scope.stop();
    for (const id of timers.keys()) clear(id);
    controllers.delete(store); unsubscribe();
  });
  controller = { busy, blocked, remove, attach(value) { bindings = value; } };
  controllers.set(store, controller);
  return controller;
}

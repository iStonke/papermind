import assert from 'node:assert/strict';
import test from 'node:test';
import { computed, ref } from 'vue';
import { createImportInboxSync } from '../src/workspaces/documents/importInboxSync.js';
import { createMetadataAutosave } from '../src/workspaces/documents/metadataAutosave.js';
import { selectPdfFiles } from '../src/workspaces/documents/pdfSelection.js';

function fakeBrowser(t) {
  const previousWindow = globalThis.window;
  const previousDocument = globalThis.document;
  const timers = new Map();
  let id = 0;
  globalThis.window = {
    ReadableStream: true,
    setTimeout(callback) { timers.set(++id, callback); return id; },
    clearTimeout(timer) { timers.delete(timer); },
  };
  globalThis.document = Object.assign(new EventTarget(), { hidden: false });
  t.after(() => { globalThis.window = previousWindow; globalThis.document = previousDocument; });
  return timers;
}

test('an inbox response arriving after disposal cannot restart polling', async (t) => {
  const timers = fakeBrowser(t);
  let finish;
  let calls = 0;
  let closed = false;
  const sync = createImportInboxSync({
    refresh: () => ++calls === 1 ? Promise.resolve() : new Promise((resolve) => { finish = resolve; }),
    subscribe: () => ({ close() { closed = true; } }),
    onPayload() {}, isOpen: () => false,
  });
  sync.start();
  await Promise.resolve();
  const [id, callback] = timers.entries().next().value;
  timers.delete(id);
  const running = callback();
  sync.dispose();
  finish();
  await running;
  assert.equal(timers.size, 0);
  assert.equal(closed, true);
});

test('autosave preserves a newer draft while an older request finishes', async (t) => {
  const timers = fakeBrowser(t);
  const previousFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = previousFetch; });
  let finish;
  globalThis.fetch = () => new Promise((resolve) => { finish = resolve; });
  const detail = ref({ id: 'doc', display_name: 'Original', document_date: null, notes: '' });
  const draft = ref('First change');
  const revision = ref(1);
  const state = {
    selectedDocumentDetail: detail, selectedDocumentId: ref('doc'), documents: ref([detail.value]),
    metadataDocName: draft, metadataDocDate: ref(''), metadataNotes: ref(''),
    metadataDraftRevision: revision, isSavingMetadata: ref(false),
    isMetadataDirty: computed(() => draft.value !== detail.value.display_name),
    metadataDocDateHasError: ref(false), metadataSuccessMessage: ref(''), metadataErrorMessage: ref(''),
    documentListQuery: { sort: 'created_at' }, isRetentionFeatureEnabled: ref(false),
  };
  const controller = createMetadataAutosave({ state, apiBaseUrl: '', actions: {
    getDocumentNameDraft: (doc) => doc.display_name,
    applyKnownFavoriteState: (doc) => doc,
    applyMetadataFromDetail: (doc) => { draft.value = doc.display_name; },
    parseResponseError: async () => 'error', fetchDocumentDetail() {}, fetchDocuments() {}, loadRetention() {},
  } });
  const saving = controller.saveMetadata({ skipDocumentReload: true, silentSuccess: true });
  draft.value = 'Newer change';
  revision.value += 1;
  finish({ ok: true, json: async () => ({ ...detail.value, display_name: 'First change' }) });
  await saving;
  assert.equal(draft.value, 'Newer change');
  assert.equal(detail.value.display_name, 'First change');
  assert.equal(timers.size, 1);
  controller.dispose();
  assert.equal(timers.size, 0);
});

test('PDF selection rejects other types and duplicate files but preserves distinct folder paths', () => {
  const first = { name: 'scan.pdf', size: 10, lastModified: 1, webkitRelativePath: 'a/scan.pdf' };
  const second = { ...first, webkitRelativePath: 'b/scan.pdf' };
  const result = selectPdfFiles([first, first, second, { name: 'notes.txt' }], 'folder');
  assert.deepEqual(result.files, [first, second]);
  assert.equal(result.skippedDuplicates, 1);
  assert.equal(result.skippedNonPdf, 1);
});

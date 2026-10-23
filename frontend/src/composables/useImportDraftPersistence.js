import { onBeforeUnmount, onMounted, ref, toRaw, watch } from 'vue';
import { apiSessionOwner, apiSessionGeneration } from '../api/session.js';
import { setImportAnalysisState } from '../utils/importProcess.js';
import { DraftConflictError, importDraftStorage } from '../utils/importDraftStorage.js';
import { scannerDraft } from '../utils/importScanDraft.js';

export function useImportDraftPersistence(store, { restored = () => {}, failed = () => {}, saved = () => {} } = {}) {
  const owner = apiSessionOwner(), generation = apiSessionGeneration();
  const conflict = ref(false);
  let ready = false, disposed = false, timer, revision = 0, failureReported = false;
  let chain = Promise.resolve();
  let resolveLoaded;
  const loaded = new Promise(resolve => { resolveLoaded = resolve; });
  const fileRefs = new WeakMap(), imageRefs = new Map(), savedAssets = new Set();
  const copy = value => JSON.parse(JSON.stringify(value));
  function reportFailure(error) {
    if (error?.name === 'DraftConflictError') conflict.value = true;
    if (!failureReported) failed(error);
    failureReported = true;
  }
  function snapshot() {
    if (!store.documents.length && !store.availableDraft && !store.availableRemovals.length) return { value: null, assets: [] };
    const assets = [], used = new Set();
    const assetRef = (value, cache) => {
      let id = cache.get(value);
      if (!id) { id = crypto.randomUUID(); cache.set(value, id); }
      used.add(id);
      if (!savedAssets.has(id)) assets.push([id, value]);
      return id;
    };
    const serializeDocuments = entries => entries.map(doc => ({
      ...copy({ ...doc, pages: undefined }),
      pages: (doc.pages || []).map(({ thumbUrl, ...page }) => ({ ...copy(page), ...(thumbUrl ? { thumbRef: assetRef(thumbUrl, imageRefs) } : {}) })),
    }));
    const serializeDraft = draft => {
      const usedSources = new Set(draft.documents.flatMap(doc => (doc.pages || []).map(page => page.sourceFileId)));
      return { batchId: draft.batchId, createdAt: draft.createdAt, documents: serializeDocuments(draft.documents),
        sourceMeta: copy(draft.sourceMeta.filter(([id]) => usedSources.has(id))),
        files: (draft.files || []).filter(([id, file]) => usedSources.has(id) && file instanceof Blob).map(([id, file]) => [id, assetRef(toRaw(file), fileRefs)]),
        pendingCommit: copy(draft.pendingCommit || null),
      };
    };
    const current = serializeDraft({ batchId: store.batchId, createdAt: store.createdAt, documents: store.documents,
      pendingCommit: store.pendingCommit, files: [...toRaw(store.stagingFiles)], sourceMeta: [...store.sourceMetaById] });
    const retained = store.availableDraft?.pendingCommit ? store.availableDraft : scannerDraft(store.availableDraft);
    const availableDraft = retained ? serializeDraft(retained) : null;
    const availableRemovals = store.availableRemovals.map(removal => ({
      ...copy({ ...removal, draft: undefined }), draft: removal.draft ? serializeDraft(removal.draft) : null,
    }));
    // Prevent removed thumbnails from accumulating in the in-memory reference map.
    for (const [image, id] of imageRefs) if (!used.has(id)) imageRefs.delete(image);
    return { assets, value: {
      version: 2, savedAt: Date.now(), ...current, availableDraft, availableRemovals, assetRefs: [...used],
    } };
  }
  function save() {
    if (!ready || conflict.value || generation !== apiSessionGeneration()) return Promise.resolve(false);
    // Build inside the queue: several keystrokes must not enqueue repeated blobs.
    chain = chain.then(async () => {
      if (conflict.value || generation !== apiSessionGeneration()) return false;
      const started = performance.now();
      const { value, assets } = snapshot();
      const result = await importDraftStorage(owner, value, true, { expectedRevision: revision, assets });
      if (!result) throw new Error('Keine lokale Entwurfssicherung verfügbar.');
      revision = result.revision;
      savedAssets.clear();
      for (const id of value?.assetRefs || []) savedAssets.add(id);
      failureReported = false;
      saved({ duration_ms: performance.now() - started, bytes: assets.reduce((sum, [, asset]) => sum + (asset instanceof Blob ? asset.size : String(asset).length * 2), 0) });
      return true;
    }).catch(error => { reportFailure(error); return false; });
    return chain;
  }
  function onPageHide() { clearTimeout(timer); void save(); }
  onMounted(async () => {
    try {
      const draft = await importDraftStorage(owner);
      if (disposed || generation !== apiSessionGeneration()) return;
      revision = Number(draft?.revision || 0);
      for (const [id, asset] of draft?.hydratedAssets || []) {
        if (asset instanceof Blob) fileRefs.set(asset, id);
        else if (typeof asset === 'string') imageRefs.set(asset, id);
        savedAssets.add(id);
      }
      if (draft?.documents.length && store.documents.length && draft.batchId !== store.batchId) throw new DraftConflictError();
      if (draft?.availableDraft && store.availableDraft && draft.availableDraft.batchId !== store.availableDraft.batchId) throw new DraftConflictError();
      if (draft?.availableDraft && !store.availableDraft) store.availableDraft = draft.availableDraft.pendingCommit ? draft.availableDraft : scannerDraft(draft.availableDraft);
      if (store.availableDraft?.pendingCommit && !store.totalPages) store.restoreAvailableDraft();
      if (draft?.availableRemovals?.length && !store.availableRemovals.length) store.availableRemovals = draft.availableRemovals.map(removal => ({ ...removal, ready: true }));
      // Closing can precede a slow initial IndexedDB read. Do not reopen or
      // overwrite that newer in-memory copy of the same batch.
      const alreadyParked = draft?.batchId && draft.batchId === store.availableDraft?.batchId;
      if (draft?.documents.length && !store.documents.length && !alreadyParked) {
        store.batchId = draft.batchId; store.createdAt = draft.createdAt;
        store.documents = draft.documents;
        store.sourceMetaById = new Map(draft.sourceMeta);
        store.stagingFiles = new Map(draft.files);
        store.pendingCommit = draft.pendingCommit || null;
        for (const doc of store.documents) {
          if (['working', 'pending_ocr'].includes(doc.meta?.titleSuggestionStatus)) setImportAnalysisState(doc.meta, 'idle');
          if (doc.meta) { doc.meta.analysisPending = false; doc.meta.analysisLookupPending = false; }
          // A remote source may expire. Preserve its metadata and pages so it can
          // be replaced/retried; never silently drop a user's draft.
          for (const page of doc.pages || []) if (!store.stagingFiles.has(page.sourceFileId) && !page.thumbUrl) page.previewError = true;
        }
        restored();
      }
      ready = true;
      void save();
    } catch (error) {
      // A failed read must never overwrite a draft that we could not restore.
      reportFailure(error);
    } finally { resolveLoaded(); }
    window.addEventListener('pagehide', onPageHide);
    document.addEventListener('visibilitychange', onVisibility);
  });
  function onVisibility() { if (document.visibilityState === 'hidden') onPageHide(); }
  const stop = watch(() => [store.documents, store.pendingCommit, [...store.sourceMetaById], [...store.stagingFiles], store.availableDraft, store.availableRemovals], () => {
    clearTimeout(timer); timer = setTimeout(save, 300);
  }, { deep: true });
  onBeforeUnmount(() => {
    clearTimeout(timer); void save(); stop(); disposed = true;
    window.removeEventListener('pagehide', onPageHide);
    document.removeEventListener('visibilitychange', onVisibility);
  });
  return { save, conflict, loaded };
}

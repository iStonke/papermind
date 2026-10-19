import { onBeforeUnmount, onMounted, toRaw, watch } from 'vue';
import { apiSessionOwner, apiSessionGeneration } from '../api/session.js';
import { importDraftStorage } from '../utils/importDraftStorage.js';

export function useImportDraftPersistence(store, { restored = () => {}, failed = () => {} } = {}) {
  const owner = apiSessionOwner();
  const generation = apiSessionGeneration();
  let ready = false;
  let disposed = false;
  let timer;
  let chain = Promise.resolve();
  let failureReported = false;
  function reportFailure(error) {
    if (!failureReported) failed(error);
    failureReported = true;
  }
  function save() {
    if (!ready || generation !== apiSessionGeneration()) return;
    const value = store.documents.length ? {
      version: 1, savedAt: Date.now(), batchId: store.batchId, createdAt: store.createdAt,
      documents: JSON.parse(JSON.stringify(store.documents)),
      sourceMeta: JSON.parse(JSON.stringify([...store.sourceMetaById])),
      files: [...toRaw(store.stagingFiles)], pendingCommit: JSON.parse(JSON.stringify(store.pendingCommit)),
    } : null;
    chain = chain.then(async () => { await importDraftStorage(owner, value, true); failureReported = false; }).catch(reportFailure);
    return chain;
  }
  onMounted(async () => {
    try {
      const draft = await importDraftStorage(owner);
      if (disposed || generation !== apiSessionGeneration()) return;
      if (draft?.version === 1 && !store.documents.length) {
        store.batchId = draft.batchId;
        store.createdAt = draft.createdAt;
        store.documents = draft.documents;
        store.sourceMetaById = new Map(draft.sourceMeta);
        store.stagingFiles = new Map(draft.files);
        store.pendingCommit = draft.pendingCommit;
        for (const doc of store.documents) {
          if (['working', 'pending_ocr'].includes(doc.meta?.titleSuggestionStatus)) doc.meta.titleSuggestionStatus = 'idle';
        }
        restored();
      }
    } catch (error) { reportFailure(error); }
    ready = true;
    save();
  });
  const stop = watch(() => [store.documents, store.pendingCommit, [...store.sourceMetaById]], () => {
    clearTimeout(timer);
    timer = setTimeout(save, 200);
  }, { deep: true });
  onBeforeUnmount(() => { clearTimeout(timer); save(); stop(); disposed = true; });
  return { save };
}

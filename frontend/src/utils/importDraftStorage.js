const DATABASE = 'papermind-import-drafts';
export class DraftConflictError extends Error {
  constructor() { super('Der Importentwurf wurde in einem anderen Fenster geändert.'); this.name = 'DraftConflictError'; }
}
export function migrateImportDraft(draft) {
  if (!draft) return null;
  if (![1, 2].includes(draft.version) || !Array.isArray(draft.documents) || !Array.isArray(draft.sourceMeta)) {
    throw new Error('Unbekanntes oder beschädigtes Importentwurfsformat.');
  }
  const pairs = value => Array.isArray(value) && value.every(entry => Array.isArray(entry) && entry.length === 2 && typeof entry[0] === 'string');
  const validDraft = value => value && Array.isArray(value.documents) && value.documents.every(doc => doc && typeof doc === 'object' && Array.isArray(doc.pages) && doc.pages.every(page => page && typeof page === 'object'))
    && pairs(value.sourceMeta) && pairs(value.files || []);
  if (!validDraft(draft) || draft.availableDraft != null && !validDraft(draft.availableDraft)
    || draft.availableRemovals != null && (!Array.isArray(draft.availableRemovals) || !draft.availableRemovals.every(removal =>
      removal && typeof removal.id === 'string' && Number.isFinite(removal.expiresAt) && removal.expiresAt > 0
      && Number.isSafeInteger(removal.pageCount) && removal.pageCount > 0
      && (removal.draft == null || validDraft(removal.draft)) && Array.isArray(removal.items)
      && removal.items.every(item => item && typeof item.id === 'string' && typeof item.source_file_id === 'string')))
    || draft.version === 2 && (!Array.isArray(draft.assetRefs) || !draft.assetRefs.every(id => typeof id === 'string'))
    || !Number.isSafeInteger(Number(draft.revision || 0)) || Number(draft.revision || 0) < 0) {
    throw new Error('Beschädigter Importentwurf. Der gespeicherte Stand wurde nicht überschrieben.');
  }
  return { ...draft, revision: Number(draft.revision || 0) };
}
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 2);
    let blocked = false;
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('drafts')) db.createObjectStore('drafts');
      if (!db.objectStoreNames.contains('assets')) db.createObjectStore('assets').createIndex('owner', 'owner');
    };
    request.onsuccess = () => {
      if (blocked) { request.result.close(); return; }
      request.result.onversionchange = () => request.result.close(); resolve(request.result);
    };
    request.onerror = () => reject(request.error);
    request.onblocked = () => { blocked = true; reject(new Error('Die Entwurfssicherung wird von einem älteren Fenster blockiert.')); };
  });
}
// Metadata and new immutable assets commit atomically. Failed/quota transactions
// leave the last complete draft intact. expectedRevision provides cross-tab CAS.
export async function importDraftStorage(owner, value, write = false, { expectedRevision, assets = [] } = {}) {
  if (!owner || typeof indexedDB === 'undefined') return null;
  // WebKit can reject native File/Blob objects in an IndexedDB transaction.
  // Serialize each new immutable file once, before opening the transaction.
  const storedAssets = await Promise.all(assets.map(async ([id, asset]) => [id, asset instanceof Blob
    ? { kind: 'file', data: await asset.arrayBuffer(), name: asset.name || 'Dokument.pdf', type: asset.type, lastModified: asset.lastModified || 0 } : asset]));
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(['drafts', 'assets'], write ? 'readwrite' : 'readonly');
      const drafts = tx.objectStore('drafts'), assetStore = tx.objectStore('assets');
      let result = null, failure, hydrate = () => {};
      tx.oncomplete = () => { try { hydrate(); resolve(result); } catch (error) { reject(error); } };
      tx.onerror = event => reject(failure || event.target?.error || tx.error || new Error('Entwurf konnte nicht gespeichert werden.'));
      tx.onabort = () => reject(failure || tx.error || new Error('Entwurf konnte nicht gespeichert werden.'));
      const request = drafts.get(owner);
      request.onsuccess = () => {
        try {
          let previous;
          try { previous = migrateImportDraft(request.result); }
          catch (error) { failure = error; tx.abort(); return; }
          if (write) {
            if (expectedRevision !== undefined && Number(previous?.revision || 0) !== expectedRevision) {
              failure = new DraftConflictError(); tx.abort(); return;
            }
            const revision = Number(previous?.revision || 0) + 1;
            // Keep a revision tombstone, so deletion cannot reset the CAS counter.
            drafts.put(value ? { ...value, revision } : { version: 2, revision, documents: [], sourceMeta: [], files: [], assetRefs: [] }, owner);
            for (const [id, asset] of storedAssets) assetStore.put({ owner, value: asset }, [owner, id]);
            const used = new Set(value?.assetRefs || []);
            const cursor = assetStore.index('owner').openKeyCursor(IDBKeyRange.only(owner));
            cursor.onsuccess = () => { const row = cursor.result; if (!row) return;
              if (!used.has(row.primaryKey[1])) assetStore.delete(row.primaryKey); row.continue(); };
            result = { revision };
          } else {
            if (!previous?.documents.length && !previous?.availableDraft?.documents.length && !previous?.availableRemovals?.some(removal => removal.draft?.documents.length)) { result = previous; return; }
            result = previous;
            if (previous.version === 2) {
              const loaded = new Map();
              for (const id of previous.assetRefs || []) {
                const asset = assetStore.get([owner, id]);
                asset.onsuccess = () => {
                  if (!asset.result) return;
                  const value = asset.result.value;
                  loaded.set(id, value?.kind === 'file' && value.data instanceof ArrayBuffer
                    ? new File([value.data], value.name, { type: value.type, lastModified: value.lastModified }) : value);
                };
              }
              hydrate = () => {
                Object.defineProperty(result, 'hydratedAssets', { value: loaded });
                for (const draft of [result, result.availableDraft, ...(result.availableRemovals || []).map(removal => removal.draft)].filter(Boolean)) {
                  draft.files = (draft.files || []).map(([id, ref]) => [id, loaded.get(ref)]).filter(([, file]) => file instanceof Blob);
                  for (const doc of draft.documents) for (const page of doc.pages || []) {
                    page.thumbUrl = loaded.get(page.thumbRef) || ''; delete page.thumbRef;
                  }
                }
              };
            }
          }
        } catch (error) { failure = error; try { tx.abort(); } catch { /* already aborted */ } }
      };
    });
  } finally { db.close(); }
}

const DB_NAME = 'papermind-local-drafts';
const DB_VERSION = 1;
const STORE_NAME = 'note-drafts';

let databasePromise = null;

function openDatabase() {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('Lokale Entwurfsablage ist nicht verfügbar.'));
  }
  if (databasePromise) return databasePromise;

  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'noteId' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Lokale Entwurfsablage konnte nicht geöffnet werden.'));
    request.onblocked = () => reject(new Error('Lokale Entwurfsablage ist blockiert.'));
  }).catch((error) => {
    databasePromise = null;
    throw error;
  });

  return databasePromise;
}

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Lokaler Entwurf konnte nicht verarbeitet werden.'));
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error('Lokaler Entwurf konnte nicht gespeichert werden.'));
    transaction.onabort = () => reject(transaction.error || new Error('Lokale Entwurfsablage wurde abgebrochen.'));
  });
}

export function createNoteDraftVersion() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `draft-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.keys(value)
      .sort()
      .map((key) => [key, canonicalJson(value[key])]),
  );
}

export function noteBodiesEqual(left, right) {
  return JSON.stringify(canonicalJson(left || null))
    === JSON.stringify(canonicalJson(right || null));
}

export function noteDraftMatchesServer(draft, note) {
  if (!draft || !note) return false;
  return String(draft.title || '') === String(note.title || '')
    && noteBodiesEqual(draft.bodyJson, note.body_json);
}

export function latestKnownNoteRevision(...values) {
  return values.reduce(
    (latest, value) => Math.max(latest, Math.max(1, Number(value) || 1)),
    1,
  );
}

export function normalizeNoteDraftForStorage(draft) {
  return {
    noteId: String(draft.noteId),
    title: String(draft.title || ''),
    bodyJson: draft.bodyJson || null,
    baseRevision: Math.max(1, Number(draft.baseRevision) || 1),
    clientVersion: String(draft.clientVersion),
    savedAt: Number(draft.savedAt) || Date.now(),
  };
}

export async function getNoteDraft(noteId) {
  if (!noteId) return null;
  const db = await openDatabase();
  const transaction = db.transaction(STORE_NAME, 'readonly');
  return (await requestResult(transaction.objectStore(STORE_NAME).get(String(noteId)))) || null;
}

export async function putNoteDraft(draft) {
  if (!draft?.noteId || !draft?.clientVersion) {
    throw new Error('Lokaler Entwurf ist unvollständig.');
  }
  const db = await openDatabase();
  const transaction = db.transaction(STORE_NAME, 'readwrite');
  // Nur serialisierbare Nutzdaten ablegen. Der Editor hängt während des
  // Schreibens vorübergehend Promises an sein Snapshot-Objekt.
  transaction.objectStore(STORE_NAME).put(normalizeNoteDraftForStorage(draft));
  await transactionDone(transaction);
  return true;
}

export async function deleteNoteDraft(noteId, expectedClientVersion = null) {
  if (!noteId) return false;
  const db = await openDatabase();
  const transaction = db.transaction(STORE_NAME, 'readwrite');
  const store = transaction.objectStore(STORE_NAME);
  if (expectedClientVersion) {
    const current = await requestResult(store.get(String(noteId)));
    if (current?.clientVersion !== expectedClientVersion) {
      transaction.abort();
      return false;
    }
  }
  store.delete(String(noteId));
  await transactionDone(transaction);
  return true;
}

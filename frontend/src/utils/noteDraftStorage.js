const DB_NAME = 'papermind-local-drafts';
const DB_VERSION = 1;
const STORE_NAME = 'note-drafts';

// Ein hängender IndexedDB-Zugriff (z. B. eine von einem anderen Tab gehaltene
// oder vom Browser geschlossene Verbindung) darf das Umschalten von Notizen nie
// blockieren: Jeder Zugriff hat eine Zeitgrenze, danach wird die Verbindung
// verworfen und beim nächsten Zugriff neu geöffnet.
export const NOTE_DRAFT_OPEN_TIMEOUT_MS = 3000;
export const NOTE_DRAFT_READ_TIMEOUT_MS = 1500;
export const NOTE_DRAFT_WRITE_TIMEOUT_MS = 5000;
// Nach einer Zeitüberschreitung beim Lesen wird eine Weile gar nicht mehr
// gewartet, damit nicht jeder Notizwechsel erneut verzögert wird.
export const NOTE_DRAFT_READ_PAUSE_MS = 60000;

let databasePromise = null;
let readsPausedUntil = 0;

function resetDatabase() {
  databasePromise = null;
}

export function withNoteDraftTimeout(promise, ms, message) {
  let timer = null;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

function openDatabase() {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('Lokale Entwurfsablage ist nicht verfügbar.'));
  }
  if (databasePromise) return databasePromise;

  let abandoned = false;
  databasePromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'noteId' });
      }
    };
    request.onsuccess = () => {
      const db = request.result;
      // Zu spät geöffnet (Zeitgrenze schon abgelaufen): Verbindung nicht liegen lassen.
      if (abandoned) {
        db.close();
        return;
      }
      // Andere Tabs (neuere Version) oder der Browser schließen die Verbindung:
      // dann nicht weiter auf die tote Verbindung warten.
      db.onversionchange = () => {
        db.close();
        resetDatabase();
      };
      db.onclose = resetDatabase;
      resolve(db);
    };
    request.onerror = () => reject(request.error || new Error('Lokale Entwurfsablage konnte nicht geöffnet werden.'));
    request.onblocked = () => reject(new Error('Lokale Entwurfsablage ist blockiert.'));
  });
  databasePromise = withNoteDraftTimeout(
    databasePromise,
    NOTE_DRAFT_OPEN_TIMEOUT_MS,
    'Lokale Entwurfsablage antwortet nicht.',
  ).catch((error) => {
    abandoned = true;
    resetDatabase();
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
    && Boolean(draft.titleIsGenerated) === Boolean(note.title_is_generated)
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
    titleIsGenerated: Boolean(draft.titleIsGenerated),
    bodyJson: draft.bodyJson || null,
    baseRevision: Math.max(1, Number(draft.baseRevision) || 1),
    clientVersion: String(draft.clientVersion),
    savedAt: Number(draft.savedAt) || Date.now(),
  };
}

/** Datenbankzugriff mit Zeitgrenze; eine hängende Verbindung wird verworfen. */
function guarded(operation, ms, message) {
  return withNoteDraftTimeout(operation(), ms, message).catch((error) => {
    resetDatabase();
    throw error;
  });
}

export function getNoteDraft(noteId) {
  if (!noteId) return Promise.resolve(null);
  if (Date.now() < readsPausedUntil) {
    return Promise.reject(new Error('Lokale Entwurfsablage antwortet zurzeit nicht.'));
  }
  return guarded(async () => {
    const db = await openDatabase();
    const transaction = db.transaction(STORE_NAME, 'readonly');
    return (await requestResult(transaction.objectStore(STORE_NAME).get(String(noteId)))) || null;
  }, NOTE_DRAFT_READ_TIMEOUT_MS, 'Lokaler Entwurf konnte nicht rechtzeitig gelesen werden.').then(
    (draft) => {
      readsPausedUntil = 0;
      return draft;
    },
    (error) => {
      if (/nicht rechtzeitig|antwortet nicht/.test(error?.message || '')) {
        readsPausedUntil = Date.now() + NOTE_DRAFT_READ_PAUSE_MS;
      }
      throw error;
    },
  );
}

/** Nur für Tests: Lesepause nach Zeitüberschreitung aufheben. */
export function resetNoteDraftReadPause() {
  readsPausedUntil = 0;
}

export async function putNoteDraft(draft) {
  if (!draft?.noteId || !draft?.clientVersion) {
    throw new Error('Lokaler Entwurf ist unvollständig.');
  }
  return guarded(() => writeNoteDraft(draft), NOTE_DRAFT_WRITE_TIMEOUT_MS, 'Lokaler Entwurf konnte nicht rechtzeitig gespeichert werden.');
}

async function writeNoteDraft(draft) {
  const db = await openDatabase();
  const transaction = db.transaction(STORE_NAME, 'readwrite');
  // Nur serialisierbare Nutzdaten ablegen. Der Editor hängt während des
  // Schreibens vorübergehend Promises an sein Snapshot-Objekt.
  transaction.objectStore(STORE_NAME).put(normalizeNoteDraftForStorage(draft));
  await transactionDone(transaction);
  return true;
}

export function deleteNoteDraft(noteId, expectedClientVersion = null) {
  if (!noteId) return Promise.resolve(false);
  return guarded(() => removeNoteDraft(noteId, expectedClientVersion), NOTE_DRAFT_WRITE_TIMEOUT_MS, 'Lokaler Entwurf konnte nicht rechtzeitig entfernt werden.');
}

async function removeNoteDraft(noteId, expectedClientVersion) {
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

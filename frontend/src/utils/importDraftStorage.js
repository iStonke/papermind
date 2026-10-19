const DATABASE = 'papermind-import-drafts';
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('drafts');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function importDraftStorage(owner, value, write = false) {
  if (!owner || typeof indexedDB === 'undefined') return null;
  const database = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction('drafts', write ? 'readwrite' : 'readonly');
      const storage = transaction.objectStore('drafts');
      const request = write ? value ? storage.put(value, owner) : storage.delete(owner) : storage.get(owner);
      transaction.oncomplete = () => resolve(write ? null : request.result || null);
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error || new Error('Entwurf konnte nicht gespeichert werden.'));
    });
  } finally { database.close(); }
}

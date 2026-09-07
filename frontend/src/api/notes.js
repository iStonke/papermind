import { apiDelete, apiFetch, apiGet, apiPatch, apiPost, apiPut, authHeaders, getBaseUrl } from './client.js';

export const listNotes = ({ inTrash = false, documentId = null, dossierId = null, tagId = null, collectionId = null, notebookId = null, noNotebook = false, favoritesOnly = false, templates = false, q = '', searchScope = 'all' } = {}) => {
  const params = new URLSearchParams();
  if (inTrash) params.set('in_trash', 'true');
  if (documentId) params.set('document_id', documentId);
  if (dossierId) params.set('dossier_id', dossierId);
  if (tagId) params.set('tag_id', tagId);
  // Sammlung scopt die Liste (außer bei Vorlagen – dort ignoriert der Server sie).
  if (collectionId) params.set('collection_id', collectionId);
  if (notebookId) params.set('notebook_id', notebookId);
  if (noNotebook) params.set('no_notebook', 'true');
  if (favoritesOnly) params.set('favorites_only', 'true');
  if (templates) params.set('templates', 'true');
  if (String(q || '').trim()) params.set('q', String(q).trim());
  if (searchScope && searchScope !== 'all') params.set('search_scope', searchScope);
  const suffix = params.toString();
  return apiGet(`/api/notes${suffix ? `?${suffix}` : ''}`);
};

// --- Sammlungen (oberste Ebene, harte Partition) ---------------------------
export const listCollections = () => apiGet('/api/notes/collections');
export const createCollection = (body = {}) => apiPost('/api/notes/collections', body);
export const updateCollection = (id, body = {}) => apiPatch(`/api/notes/collections/${id}`, body);
/** Löscht eine Sammlung; nicht-leere brauchen ein Ziel zum Umhängen. */
export const deleteCollection = (id, { reassignTo = null } = {}) =>
  apiDelete(`/api/notes/collections/${id}${reassignTo ? `?reassign_to=${reassignTo}` : ''}`);
/** Verschiebt Notizen in eine andere Sammlung (koppelt ihr Notizbuch ab). */
export const moveNotesToCollection = ({ ids, collectionId }) =>
  apiPost('/api/notes/collections/move', { ids, collection_id: collectionId });
/** Setzt die Reihenfolge der Sammlungen (IDs in Zielreihenfolge). */
export const reorderCollections = (ids) => apiPost('/api/notes/collections/reorder', { ids });

// --- Notizbücher (flache Ablageebene) --------------------------------------
export const listNotebooks = (collectionId = null) =>
  apiGet(`/api/notes/notebooks${collectionId ? `?collection_id=${collectionId}` : ''}`);
export const createNotebook = (body = {}) => apiPost('/api/notes/notebooks', body);
export const updateNotebook = (id, body = {}) => apiPatch(`/api/notes/notebooks/${id}`, body);
export const deleteNotebook = (id) => apiDelete(`/api/notes/notebooks/${id}`);
/** Verschiebt Notizen in ein Notizbuch (notebookId=null → aus Notizbuch nehmen). */
export const moveNotesToNotebook = ({ ids, notebookId = null }) =>
  apiPost('/api/notes/notebooks/move', { ids, notebook_id: notebookId });
/** Setzt die Reihenfolge der Notizbücher (IDs in Zielreihenfolge). */
export const reorderNotebooks = (ids) => apiPost('/api/notes/notebooks/reorder', { ids });
export const getNote = (id) => apiGet(`/api/notes/${id}`);
export const getNoteBacklinks = (id) => apiGet(`/api/notes/${id}/backlinks`);
export const createNote = (body = {}) => apiPost('/api/notes', body);
export const listNoteTemplates = () => apiGet('/api/notes/templates');
export const createNoteFromTemplate = (templateId) => apiPost(`/api/notes/from-template/${templateId}`, undefined);
export const saveNoteAsTemplate = (id, body = {}) => apiPost(`/api/notes/${id}/save-as-template`, body);

// Baustein-Vorlagen (Feldblöcke) – getrennt von den Ganz-Notiz-Vorlagen.
export const listBlockTemplates = () => apiGet('/api/notes/block-templates');
export const createBlockTemplate = (body = {}) => apiPost('/api/notes/block-templates', body);
export const updateBlockTemplate = (id, body = {}) => apiPatch(`/api/notes/block-templates/${id}`, body);
export const deleteBlockTemplate = (id) => apiDelete(`/api/notes/block-templates/${id}`);
export const patchNote = (id, body) => apiPatch(`/api/notes/${id}`, body);
export const listNoteRevisions = (id, { limit = 50 } = {}) =>
  apiGet(`/api/notes/${id}/revisions?limit=${Math.max(1, Math.min(Number(limit) || 50, 100))}`);
export const getNoteRevision = (id, revisionId) => apiGet(`/api/notes/${id}/revisions/${revisionId}`);
export const checkpointNoteRevision = (id, reason) =>
  apiPost(`/api/notes/${id}/revisions/checkpoint`, { reason });
export const restoreNoteRevision = (id, revisionId, baseRevision) =>
  apiPost(`/api/notes/${id}/revisions/${revisionId}/restore`, { base_revision: baseRevision });
export const setNoteTags = (id, { tagIds = [], tags = [] } = {}) =>
  apiPut(`/api/notes/${id}/tags`, { tag_ids: tagIds, tags });
export const trashNote = (id) => apiPost(`/api/notes/${id}/trash`, undefined);
export const restoreNote = (id) => apiPost(`/api/notes/${id}/restore`, undefined);
export const emptyNotesTrash = () => apiDelete('/api/notes/trash');
export const deleteNote = (id) => apiDelete(`/api/notes/${id}`);
export const uploadNoteImage = (id, file) => {
  const body = new FormData();
  body.append('file', file);
  return apiFetch(`/api/notes/${id}/images`, { method: 'POST', body });
};

/**
 * Sammelaktion über mehrere Notizen aus der Verwaltungsfläche.
 * @param {{ action: 'trash'|'restore'|'delete'|'template', ids: string[] }} payload
 */
export const bulkNotes = ({ action, ids }) => apiPost('/api/notes/bulk', { action, ids });

/**
 * Streamt NDJSON-Ereignisse der Notiz-Schreibassistenz. Der Callback erhält
 * Meta-, Delta- und Done-Ereignisse; API-Schlüssel bleiben vollständig im Backend.
 */
export async function streamNoteText(payload, { onEvent, signal } = {}) {
  const response = await fetch(`${getBaseUrl()}/api/notes/ai/generate`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
    signal,
  });
  if (!response.ok) {
    let message = `Textgenerierung fehlgeschlagen (${response.status}).`;
    try {
      const body = await response.json();
      message = body?.error?.message || body?.detail || message;
    } catch {
      // Statusmeldung verwenden.
    }
    throw new Error(message);
  }
  if (!response.body) throw new Error('Der Server unterstützt keine Streaming-Antwort.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const consumeLine = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === 'error') throw new Error(event.message || 'Textgenerierung fehlgeschlagen.');
    if (typeof onEvent === 'function') onEvent(event);
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) consumeLine(line);
    if (done) break;
  }
  if (buffer.trim()) consumeLine(buffer);
}

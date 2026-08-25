import { apiDelete, apiGet, apiPatch, apiPost, apiPut, authHeaders, getBaseUrl } from './client.js';

export const listNotes = ({ inTrash = false, documentId = null, dossierId = null, tagId = null, templates = false, q = '', searchScope = 'all' } = {}) => {
  const params = new URLSearchParams();
  if (inTrash) params.set('in_trash', 'true');
  if (documentId) params.set('document_id', documentId);
  if (dossierId) params.set('dossier_id', dossierId);
  if (tagId) params.set('tag_id', tagId);
  if (templates) params.set('templates', 'true');
  if (String(q || '').trim()) params.set('q', String(q).trim());
  if (searchScope && searchScope !== 'all') params.set('search_scope', searchScope);
  const suffix = params.toString();
  return apiGet(`/api/notes${suffix ? `?${suffix}` : ''}`);
};
export const getNote = (id) => apiGet(`/api/notes/${id}`);
export const getNoteBacklinks = (id) => apiGet(`/api/notes/${id}/backlinks`);
export const createNote = (body = {}) => apiPost('/api/notes', body);
export const listNoteTemplates = () => apiGet('/api/notes/templates');
export const createNoteFromTemplate = (templateId) => apiPost(`/api/notes/from-template/${templateId}`, undefined);
export const saveNoteAsTemplate = (id, body = {}) => apiPost(`/api/notes/${id}/save-as-template`, body);
export const patchNote = (id, body) => apiPatch(`/api/notes/${id}`, body);
export const setNoteTags = (id, { tagIds = [], tags = [] } = {}) =>
  apiPut(`/api/notes/${id}/tags`, { tag_ids: tagIds, tags });
export const trashNote = (id) => apiPost(`/api/notes/${id}/trash`, undefined);
export const restoreNote = (id) => apiPost(`/api/notes/${id}/restore`, undefined);
export const emptyNotesTrash = () => apiDelete('/api/notes/trash');
export const deleteNote = (id) => apiDelete(`/api/notes/${id}`);

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

import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/notes/{id}/learn-highlights – optional auf ein Dokument begrenzt. */
export const listNoteLearnHighlights = (noteId, documentId = null) =>
  apiGet(
    `/api/notes/${noteId}/learn-highlights${documentId ? `?document_id=${encodeURIComponent(documentId)}` : ''}`,
  );

/** POST /api/notes/{id}/learn-highlights */
export const createNoteLearnHighlight = (noteId, payload) =>
  apiPost(`/api/notes/${noteId}/learn-highlights`, payload);

/** PATCH /api/note-learn-highlights/{id} – nur die Bedeutung (Farbe). */
export const updateNoteLearnHighlight = (highlightId, color) =>
  apiPatch(`/api/note-learn-highlights/${highlightId}`, { color });

/** DELETE /api/note-learn-highlights/{id} */
export const deleteNoteLearnHighlight = (highlightId) =>
  apiDelete(`/api/note-learn-highlights/${highlightId}`);

/** GET /api/documents/{id}/learn-highlights – Gesamtübersicht aller Notizen. */
export const listDocumentLearnHighlights = (documentId) =>
  apiGet(`/api/documents/${documentId}/learn-highlights`);

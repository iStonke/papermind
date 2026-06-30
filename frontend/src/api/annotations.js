import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/documents/{id}/annotations */
export const listAnnotations = (documentId) =>
  apiGet(`/api/documents/${documentId}/annotations`);

/** POST /api/documents/{id}/annotations */
export const createAnnotation = (documentId, payload) =>
  apiPost(`/api/documents/${documentId}/annotations`, payload);

/** PATCH /api/annotations/{id} – Teil-Update (Farbe, Kommentar, Verknüpfung). */
export const updateAnnotation = (annotationId, payload) =>
  apiPatch(`/api/annotations/${annotationId}`, payload);

/** DELETE /api/annotations/{id} */
export const deleteAnnotation = (annotationId) =>
  apiDelete(`/api/annotations/${annotationId}`);

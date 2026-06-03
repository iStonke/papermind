import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/document-types?include_count=true */
export const listDocumentTypes = (includeCount = true) =>
  apiGet(`/api/document-types${includeCount ? '?include_count=true' : ''}`);

/** POST /api/document-types */
export const createDocumentType = (name) =>
  apiPost('/api/document-types', { name });

/** PATCH /api/document-types/{id} */
export const renameDocumentType = (id, name) =>
  apiPatch(`/api/document-types/${id}`, { name });

/** PATCH /api/document-types/{id} */
export const updateDocumentType = (id, payload) =>
  apiPatch(`/api/document-types/${id}`, payload);

/** DELETE /api/document-types/{id} */
export const deleteDocumentType = (id) =>
  apiDelete(`/api/document-types/${id}`);

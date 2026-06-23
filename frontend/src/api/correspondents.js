import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/correspondents?include_count=true */
export const listCorrespondents = (includeCount = false) =>
  apiGet(`/api/correspondents${includeCount ? '?include_count=true' : ''}`);

/** GET /api/correspondents/unresolved */
export const listUnresolvedCorrespondents = ({ limit = 200, excerptChars = 300 } = {}) =>
  apiGet(`/api/correspondents/unresolved?limit=${limit}&excerpt_chars=${excerptChars}`);

/** POST /api/correspondents/unresolved/{document_id}/ignore */
export const ignoreUnresolvedCorrespondent = (documentId, reason = null) =>
  apiPost(`/api/correspondents/unresolved/${documentId}/ignore`, { reason });

/** POST /api/correspondents */
export const createCorrespondent = (payload) =>
  apiPost('/api/correspondents', payload);

/** PATCH /api/correspondents/{id} */
export const updateCorrespondent = (correspondentId, payload) =>
  apiPatch(`/api/correspondents/${correspondentId}`, payload);

/** DELETE /api/correspondents/{id} */
export const deleteCorrespondent = (correspondentId) =>
  apiDelete(`/api/correspondents/${correspondentId}`);

/** POST /api/correspondents/{id}/unlink-documents */
export const unlinkCorrespondentDocuments = (correspondentId) =>
  apiPost(`/api/correspondents/${correspondentId}/unlink-documents`, {});

/** POST /api/correspondents/{id}/aliases */
export const addCorrespondentAlias = (correspondentId, alias) =>
  apiPost(`/api/correspondents/${correspondentId}/aliases`, { alias });

/** DELETE /api/correspondents/{id}/aliases/{alias_id} */
export const deleteCorrespondentAlias = (correspondentId, aliasId) =>
  apiDelete(`/api/correspondents/${correspondentId}/aliases/${aliasId}`);

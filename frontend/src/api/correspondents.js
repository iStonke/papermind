import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/correspondents?include_count=true */
export const listCorrespondents = (includeCount = false) =>
  apiGet(`/api/correspondents${includeCount ? '?include_count=true' : ''}`);

/** GET /api/correspondents/{id}/profile – Kennzahlen inkl. zugeordneter Personen */
export const getCorrespondentProfile = (correspondentId) =>
  apiGet(`/api/correspondents/${correspondentId}/profile`);

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

/** GET /api/correspondents/{id}/refinements – genauere Mitglieder für ein Dokument */
export const getCorrespondentRefinements = (correspondentId, documentId) =>
  apiGet(`/api/correspondents/${correspondentId}/refinements?document_id=${encodeURIComponent(documentId)}`);

/** POST /api/correspondents/{id}/merge – source geht in id auf und wird gelöscht */
export const mergeCorrespondents = (targetId, sourceId) =>
  apiPost(`/api/correspondents/${targetId}/merge`, { source_id: sourceId });

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

/** POST /api/correspondents/{id}/relations – role: predecessor | successor | acts_for | agent */
export const addCorrespondentRelation = (correspondentId, payload) =>
  apiPost(`/api/correspondents/${correspondentId}/relations`, payload);

/** DELETE /api/correspondents/{id}/relations/{relation_id} */
export const deleteCorrespondentRelation = (correspondentId, relationId) =>
  apiDelete(`/api/correspondents/${correspondentId}/relations/${relationId}`);

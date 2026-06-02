import { apiGet, apiPost } from './client.js';

/** GET /api/correspondents?include_count=true */
export const listCorrespondents = (includeCount = false) =>
  apiGet(`/api/correspondents${includeCount ? '?include_count=true' : ''}`);

/** POST /api/correspondents */
export const createCorrespondent = (payload) =>
  apiPost('/api/correspondents', payload);

/** POST /api/correspondents/{id}/aliases */
export const addCorrespondentAlias = (correspondentId, alias) =>
  apiPost(`/api/correspondents/${correspondentId}/aliases`, { alias });

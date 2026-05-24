import { apiDelete, apiGet, apiPost, apiPut } from './client.js';

/** GET /api/smart-folders */
export const listSmartFolders = () =>
  apiGet('/api/smart-folders');

/** GET /api/smart-folders/{id} */
export const getSmartFolder = (id) =>
  apiGet(`/api/smart-folders/${id}`);

/** POST /api/smart-folders */
export const createSmartFolder = (body) =>
  apiPost('/api/smart-folders', body);

/** PUT /api/smart-folders/{id} */
export const updateSmartFolder = (id, body) =>
  apiPut(`/api/smart-folders/${id}`, body);

/** DELETE /api/smart-folders/{id} */
export const deleteSmartFolder = (id) =>
  apiDelete(`/api/smart-folders/${id}`);

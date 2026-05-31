import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/categories?include_count=true */
export const listCategories = (includeCount = true) =>
  apiGet(`/api/categories${includeCount ? '?include_count=true' : ''}`);

/** POST /api/categories */
export const createCategory = (name) =>
  apiPost('/api/categories', { name });

/** PATCH /api/categories/{id} */
export const renameCategory = (id, name) =>
  apiPatch(`/api/categories/${id}`, { name });

/** DELETE /api/categories/{id} */
export const deleteCategory = (id) =>
  apiDelete(`/api/categories/${id}`);

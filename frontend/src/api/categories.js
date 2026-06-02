import {
  createDocumentType,
  deleteDocumentType,
  listDocumentTypes,
  renameDocumentType,
} from './documentTypes.js';

/** Compatibility alias for GET /api/document-types?include_count=true */
export const listCategories = (includeCount = true) =>
  listDocumentTypes(includeCount);

/** Compatibility alias for POST /api/document-types */
export const createCategory = (name) =>
  createDocumentType(name);

/** Compatibility alias for PATCH /api/document-types/{id} */
export const renameCategory = (id, name) =>
  renameDocumentType(id, name);

/** Compatibility alias for DELETE /api/document-types/{id} */
export const deleteCategory = (id) =>
  deleteDocumentType(id);

import { apiDelete, apiGet, apiPatch, apiPost, apiPut, authedUrl, getBaseUrl } from './client.js';

/** GET /api/documents?{queryString} */
export const listDocuments = (queryString) =>
  apiGet(`/api/documents?${queryString}`);

/** GET /api/smart-folders/{folderId}/documents?{queryString} */
export const listSmartFolderDocuments = (folderId, queryString) =>
  apiGet(`/api/smart-folders/${folderId}/documents?${queryString}`);

/** GET /api/documents/{id} */
export const getDocument = (id) =>
  apiGet(`/api/documents/${id}`);

/** PATCH /api/documents/{id} */
export const patchDocument = (id, body) =>
  apiPatch(`/api/documents/${id}`, body);

/** DELETE /api/documents/{id} – endgültig löschen */
export const deleteDocument = (id) =>
  apiDelete(`/api/documents/${id}`);

/** POST /api/documents/{id}/trash – in Papierkorb verschieben */
export const trashDocument = (id) =>
  apiPost(`/api/documents/${id}/trash`, undefined);

/** POST /api/documents/{id}/restore – aus Papierkorb wiederherstellen */
export const restoreDocument = (id) =>
  apiPost(`/api/documents/${id}/restore`, undefined);

/** POST /api/documents/{id}/favorite – Favoriten-Status umschalten */
export const toggleFavoriteApi = (id) =>
  apiPost(`/api/documents/${id}/favorite`, undefined);

/** POST /api/documents/{id}/mark-viewed */
export const markDocumentViewed = (id) =>
  apiPost(`/api/documents/${id}/mark-viewed`, undefined);

/** POST /api/documents/{id}/tags  – ersetzt alle Tags */
export const setDocumentTags = (id, tagIds) =>
  apiPost(`/api/documents/${id}/tags`, { tag_ids: tagIds });

/** POST /api/documents/{id}/auto-tags */
export const runAutoTags = (id) =>
  apiPost(`/api/documents/${id}/auto-tags`, undefined);

/** POST /api/documents/{id}/ocr */
export const queueOcr = (id) =>
  apiPost(`/api/documents/${id}/ocr`, undefined);

/**
 * Stößt den OCR-Backfill an: reiht OCR-Jobs für Dokumente ohne OCR ein
 * (schließt Lücken). dryRun=true liefert nur die Vorschau (keine Jobs).
 */
export const backfillOcr = ({ dryRun = false } = {}) =>
  apiPost(`/api/documents/ocr-backfill?dry_run=${dryRun ? 'true' : 'false'}`, {});

/**
 * Gibt die Datei-URL für einen Dokument zurück (kein fetch – nur URL-Builder).
 * Wird im <PdfPreview :src="..."> und für Downloads verwendet.
 */
export const documentFileUrl = (documentId, role = 'original') =>
  authedUrl(`${getBaseUrl()}/api/documents/${documentId}/file?role=${role}`);

/** Thumbnail-URL */
export const documentThumbnailUrl = (documentId) =>
  authedUrl(`${getBaseUrl()}/api/documents/${documentId}/thumbnail`);

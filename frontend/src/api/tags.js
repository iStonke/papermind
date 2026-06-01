import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/tags?include_count=true */
export const listTags = (includeCount = true) =>
  apiGet(`/api/tags${includeCount ? '?include_count=true' : ''}`);

/** POST /api/tags */
export const createTag = (name) =>
  apiPost('/api/tags', { name });

/** PATCH /api/tags/{id} */
export const renameTag = (id, name) =>
  apiPatch(`/api/tags/${id}`, { name });

/** POST /api/tags/{sourceId}/merge  – verschmilzt Source in Target */
export const mergeTag = (sourceId, targetId) =>
  apiPost(`/api/tags/${sourceId}/merge`, { target_id: targetId });

/** DELETE /api/tags/{id} */
export const deleteTag = (id) =>
  apiDelete(`/api/tags/${id}`);

/**
 * POST /api/tags/cleanup-unused – entfernt Tags, die an keinem Dokument hängen.
 * dryRun=true liefert nur die Vorschau (löscht nichts).
 * Antwort: { count, removed, dry_run, tags: [{ id, name }] }
 */
export const cleanupUnusedTags = (dryRun = false) =>
  apiPost(`/api/tags/cleanup-unused?dry_run=${dryRun ? 'true' : 'false'}`, {});

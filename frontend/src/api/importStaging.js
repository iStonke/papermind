import { apiFetch } from './client.js';

const SUGGEST_TITLE_TIMEOUT_MS = 90_000;

export function readImportStageAnalysis(stageId, { sourceFileIds, documentRevision, signal }) {
  const query = new URLSearchParams({ documentRevision });
  for (const sourceId of sourceFileIds) query.append('sourceFileIds', sourceId);
  return apiFetch(`/api/import/stages/${encodeURIComponent(stageId)}/analysis?${query}`, { signal, timeoutMs: 10000 });
}

export async function suggestImportStageTitle(_apiBaseUrl, stageId, { sourceFileIds = [], pageScope = 'first_page', pages = [], documentRevision = null, force = false, repeatOcr = false, signal } = {}) {
  const normalizedStageId = String(stageId || '').trim();
  if (!normalizedStageId) throw new Error('stageId is required');

  const normalizedSourceIds = Array.isArray(sourceFileIds)
    ? sourceFileIds.map((id) => String(id || '').trim()).filter(Boolean)
    : [];
  if (normalizedSourceIds.length === 0) throw new Error('sourceFileIds is required');

  const normalizedScope = String(pageScope || '').trim().toLowerCase() === 'all_pages' ? 'all_pages' : 'first_page';

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SUGGEST_TITLE_TIMEOUT_MS);
  const abort = () => controller.abort();
  if (signal?.aborted) abort();
  else signal?.addEventListener('abort', abort, { once: true });
  try {
    return await apiFetch(`/api/import/stages/${encodeURIComponent(normalizedStageId)}/suggest-title`, {
      method: 'POST',
      body: JSON.stringify({ sourceFileIds: normalizedSourceIds, pageScope: normalizedScope, pages, documentRevision, force, repeatOcr }),
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}

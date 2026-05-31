import { apiFetch, getBaseUrl } from './client.js';

const SUGGEST_TITLE_TIMEOUT_MS = 90_000;

export async function suggestImportStageTitle(_apiBaseUrl, stageId, { sourceFileIds = [], pageScope = 'first_page' } = {}) {
  const normalizedStageId = String(stageId || '').trim();
  if (!normalizedStageId) throw new Error('stageId is required');

  const normalizedSourceIds = Array.isArray(sourceFileIds)
    ? sourceFileIds.map((id) => String(id || '').trim()).filter(Boolean)
    : [];
  if (normalizedSourceIds.length === 0) throw new Error('sourceFileIds is required');

  const normalizedScope = String(pageScope || '').trim().toLowerCase() === 'all_pages' ? 'all_pages' : 'first_page';

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SUGGEST_TITLE_TIMEOUT_MS);
  try {
    return await apiFetch(`/api/import/stages/${encodeURIComponent(normalizedStageId)}/suggest-title`, {
      method: 'POST',
      body: JSON.stringify({ sourceFileIds: normalizedSourceIds, pageScope: normalizedScope }),
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

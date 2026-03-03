function normalizeApiBaseUrl(apiBaseUrl = '') {
  const normalized = String(apiBaseUrl || '').trim().replace(/\/$/, '');
  if (normalized) {
    return normalized;
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return '';
}

async function parseApiError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function suggestImportStageTitle(apiBaseUrl, stageId, { sourceFileIds = [], pageScope = 'first_page' } = {}) {
  const normalizedStageId = String(stageId || '').trim();
  if (!normalizedStageId) {
    throw new Error('stageId is required');
  }
  const normalizedSourceIds = Array.isArray(sourceFileIds)
    ? sourceFileIds.map((id) => String(id || '').trim()).filter(Boolean)
    : [];
  if (normalizedSourceIds.length === 0) {
    throw new Error('sourceFileIds is required');
  }

  const normalizedScope = String(pageScope || '').trim().toLowerCase() === 'all_pages' ? 'all_pages' : 'first_page';
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const response = await fetch(`${baseUrl}/api/import/stages/${encodeURIComponent(normalizedStageId)}/suggest-title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sourceFileIds: normalizedSourceIds,
      pageScope: normalizedScope
    })
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

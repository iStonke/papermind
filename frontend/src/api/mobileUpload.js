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

export async function createMobileUploadSession(apiBaseUrl, { maxFiles, targetStageId } = {}) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const response = await fetch(`${baseUrl}/api/mobile-upload/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      maxFiles: Number(maxFiles) > 0 ? Number(maxFiles) : undefined,
      targetStageId: String(targetStageId || '').trim() || undefined
    })
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function getMobileUploadStatus(apiBaseUrl, sessionId, { token } = {}) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const search = new URLSearchParams();
  if (token) {
    search.set('t', String(token));
  }
  const query = search.toString();
  const suffix = query ? `?${query}` : '';

  const response = await fetch(`${baseUrl}/api/mobile-upload/${encodeURIComponent(sessionId)}/status${suffix}`);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function uploadMobileFiles(apiBaseUrl, sessionId, files, { token } = {}) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const formData = new FormData();
  for (const file of files || []) {
    formData.append('files', file);
  }

  const search = new URLSearchParams();
  if (token) {
    search.set('t', String(token));
  }
  const query = search.toString();
  const suffix = query ? `?${query}` : '';

  const response = await fetch(`${baseUrl}/api/mobile-upload/${encodeURIComponent(sessionId)}/files${suffix}`, {
    method: 'POST',
    headers: token ? { 'X-Upload-Token': String(token) } : undefined,
    body: formData
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

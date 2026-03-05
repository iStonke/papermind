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

/**
 * @typedef {Object} ScanStatus
 * @property {string} jobId
 * @property {'receiving'|'processing'|'ready'|'error'} state
 * @property {'convert'|'detect'|'warp'|'clean'|'pdf'} step
 * @property {number} progress
 * @property {number} pagesTotal
 * @property {number} pagesDone
 * @property {string[]} recentFiles
 * @property {string|null} error
 */

async function parseApiError(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function createPhoneScanSession(apiBaseUrl, { maxFiles, stageId } = {}) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const response = await fetch(`${baseUrl}/api/phone-scan/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      maxFiles: Number(maxFiles) > 0 ? Number(maxFiles) : undefined,
      stageId: String(stageId || '').trim() || undefined
    })
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function getPhoneScanStatus(apiBaseUrl, token) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const normalizedToken = String(token || '').trim();
  if (!normalizedToken) {
    throw new Error('Upload token is missing.');
  }
  const search = new URLSearchParams({ token: normalizedToken });
  const response = await fetch(`${baseUrl}/api/phone-scan/status?${search.toString()}`);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function uploadPhoneScanFiles(apiBaseUrl, token, files, meta = null) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const normalizedToken = String(token || '').trim();
  if (!normalizedToken) {
    throw new Error('Upload token is missing.');
  }
  const formData = new FormData();
  for (const file of files || []) {
    formData.append('files', file);
  }
  if (meta && typeof meta === 'object') {
    formData.append('meta', JSON.stringify(meta));
  }
  const search = new URLSearchParams({ token: normalizedToken });
  const response = await fetch(`${baseUrl}/api/phone-scan/upload?${search.toString()}`, {
    method: 'POST',
    body: formData
  });
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function getPhoneScanJobStatus(apiBaseUrl, jobId) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const normalizedJobId = String(jobId || '').trim();
  if (!normalizedJobId) {
    throw new Error('Job-ID fehlt.');
  }
  const response = await fetch(`${baseUrl}/api/phone-scan/status/${encodeURIComponent(normalizedJobId)}`);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export function subscribePhoneScanJobEvents(apiBaseUrl, jobId, { onStatus, onError } = {}) {
  const baseUrl = normalizeApiBaseUrl(apiBaseUrl);
  const normalizedJobId = String(jobId || '').trim();
  if (!normalizedJobId) {
    throw new Error('Job-ID fehlt.');
  }
  const source = new EventSource(`${baseUrl}/api/phone-scan/events/${encodeURIComponent(normalizedJobId)}`);
  source.onmessage = (event) => {
    try {
      const payload = JSON.parse(String(event?.data || '{}'));
      onStatus?.(payload);
    } catch (error) {
      onError?.(error);
    }
  };
  source.onerror = (error) => {
    onError?.(error);
  };
  return source;
}

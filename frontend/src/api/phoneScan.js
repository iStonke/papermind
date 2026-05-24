import { apiFetch, getBaseUrl } from './client.js';

export async function createPhoneScanSession(_apiBaseUrl, { maxFiles, stageId } = {}) {
  return apiFetch('/api/phone-scan/session', {
    method: 'POST',
    body: JSON.stringify({
      maxFiles: Number(maxFiles) > 0 ? Number(maxFiles) : undefined,
      stageId: String(stageId || '').trim() || undefined
    })
  });
}

export async function getPhoneScanStatus(_apiBaseUrl, token) {
  const normalizedToken = String(token || '').trim();
  if (!normalizedToken) throw new Error('Upload token is missing.');
  return apiFetch(`/api/phone-scan/status?${new URLSearchParams({ token: normalizedToken })}`);
}

export async function uploadPhoneScanFiles(_apiBaseUrl, token, files, meta = null) {
  const normalizedToken = String(token || '').trim();
  if (!normalizedToken) throw new Error('Upload token is missing.');

  const formData = new FormData();
  for (const file of files || []) formData.append('files', file);
  if (meta && typeof meta === 'object') formData.append('meta', JSON.stringify(meta));

  return apiFetch(`/api/phone-scan/upload?${new URLSearchParams({ token: normalizedToken })}`, {
    method: 'POST',
    body: formData
  });
}

export async function getPhoneScanJobStatus(_apiBaseUrl, jobId) {
  const normalizedJobId = String(jobId || '').trim();
  if (!normalizedJobId) throw new Error('Job-ID fehlt.');
  return apiFetch(`/api/phone-scan/status/${encodeURIComponent(normalizedJobId)}`);
}

export function subscribePhoneScanJobEvents(_apiBaseUrl, jobId, { onStatus, onError } = {}) {
  const normalizedJobId = String(jobId || '').trim();
  if (!normalizedJobId) throw new Error('Job-ID fehlt.');

  const source = new EventSource(`${getBaseUrl()}/api/phone-scan/events/${encodeURIComponent(normalizedJobId)}`);
  source.onmessage = (event) => {
    try { onStatus?.(JSON.parse(String(event?.data || '{}'))); }
    catch (error) { onError?.(error); }
  };
  source.onerror = (error) => onError?.(error);
  return source;
}

import { apiFetch, getBaseUrl } from './client.js';

export async function createMobileUploadSession(_apiBaseUrl, { maxFiles, targetStageId } = {}) {
  return apiFetch('/api/mobile-upload/sessions', {
    method: 'POST',
    body: JSON.stringify({
      maxFiles: Number(maxFiles) > 0 ? Number(maxFiles) : undefined,
      targetStageId: String(targetStageId || '').trim() || undefined
    })
  });
}

export async function getMobileUploadStatus(_apiBaseUrl, sessionId, { token } = {}) {
  const search = new URLSearchParams();
  if (token) search.set('t', String(token));
  const suffix = search.toString() ? `?${search}` : '';
  return apiFetch(`/api/mobile-upload/${encodeURIComponent(sessionId)}/status${suffix}`);
}

export async function uploadMobileFiles(_apiBaseUrl, sessionId, files, { token } = {}) {
  const formData = new FormData();
  for (const file of files || []) formData.append('files', file);

  const search = new URLSearchParams();
  if (token) search.set('t', String(token));
  const suffix = search.toString() ? `?${search}` : '';

  return apiFetch(`/api/mobile-upload/${encodeURIComponent(sessionId)}/files${suffix}`, {
    method: 'POST',
    headers: token ? { 'X-Upload-Token': String(token) } : {},
    body: formData
  });
}

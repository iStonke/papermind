import { apiGet, apiPost, apiDelete, authHeaders, getBaseUrl } from './client.js';

/**
 * GET /api/jobs/activity – aktive (queued/running) und kürzlich fehlgeschlagene
 * Jobs über alle Dokumente, plus Zähler. Speist den Header-Aktivitätsindikator.
 * Antwort: { summary: { queued, running, failed }, jobs: [{ id, type, status, progress, document_title, error_message, ... }] }
 */
export const getJobActivity = () => apiGet('/api/jobs/activity');

/** DELETE /api/jobs/{id} – einen fehlgeschlagenen/abgeschlossenen Job aus der Anzeige entfernen. */
export const dismissJob = (jobId) =>
  apiDelete(`/api/jobs/${encodeURIComponent(String(jobId || '').trim())}`);

/** POST /api/jobs/activity/dismiss-failed – alle fehlgeschlagenen Jobs entfernen. */
export const dismissFailedJobs = () => apiPost('/api/jobs/activity/dismiss-failed');

export const createNoteAudioExport = (noteId, payload) =>
  apiPost(`/api/notes/${encodeURIComponent(String(noteId || '').trim())}/audio-exports`, payload);

export const cancelNoteAudioExport = (jobId) =>
  apiPost(`/api/note-audio-jobs/${encodeURIComponent(String(jobId || '').trim())}/cancel`);

export const retryNoteAudioExport = (jobId) =>
  apiPost(`/api/note-audio-jobs/${encodeURIComponent(String(jobId || '').trim())}/retry`);

export const dismissNoteAudioExport = (jobId) =>
  apiDelete(`/api/note-audio-jobs/${encodeURIComponent(String(jobId || '').trim())}`);

export async function downloadNoteAudioExport(jobId) {
  const response = await fetch(
    `${getBaseUrl()}/api/note-audio-jobs/${encodeURIComponent(String(jobId || '').trim())}/download`,
    { credentials: 'include', cache: 'no-store', headers: authHeaders() },
  );
  if (!response.ok) throw new Error('Die Audiodatei konnte nicht heruntergeladen werden.');
  return response.blob();
}

export const confirmNoteAudioExportDownload = (jobId) =>
  apiPost(`/api/note-audio-jobs/${encodeURIComponent(String(jobId || '').trim())}/downloaded`);

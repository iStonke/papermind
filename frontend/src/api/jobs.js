import { apiGet, apiPost, apiDelete } from './client.js';

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

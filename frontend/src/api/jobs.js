import { apiGet } from './client.js';

/**
 * GET /api/jobs/activity – aktive (queued/running) und kürzlich fehlgeschlagene
 * Jobs über alle Dokumente, plus Zähler. Speist den Header-Aktivitätsindikator.
 * Antwort: { summary: { queued, running, failed }, jobs: [{ id, type, status, progress, document_title, error_message, ... }] }
 */
export const getJobActivity = () => apiGet('/api/jobs/activity');

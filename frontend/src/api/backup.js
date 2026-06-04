import { apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/backup – Konfiguration (Passwort maskiert) + Status */
export const getBackupStatus = () => apiGet('/api/backup');

/** PATCH /api/backup – Konfiguration aktualisieren */
export const updateBackupConfig = (payload) => apiPatch('/api/backup', payload);

/** POST /api/backup/test – NAS-Verbindung testen */
export const testBackupConnection = () => apiPost('/api/backup/test', {});

/** POST /api/backup/run – Backup jetzt starten */
export const runBackupNow = () => apiPost('/api/backup/run', {});

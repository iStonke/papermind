import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/backup – Konfiguration (Passwort maskiert) + Status */
export const getBackupStatus = () => apiGet('/api/backup');

/** PATCH /api/backup – Konfiguration aktualisieren */
export const updateBackupConfig = (payload) => apiPatch('/api/backup', payload);

/** POST /api/backup/test – NAS-Verbindung testen */
export const testBackupConnection = () => apiPost('/api/backup/test', {});

/** POST /api/backup/run – Backup jetzt starten */
export const runBackupNow = () => apiPost('/api/backup/run', {});

/** GET /api/backup/archives – vorhandene Backups auf dem NAS */
export const listBackupArchives = () => apiGet('/api/backup/archives');

/** DELETE /api/backup/archives/{name} – ein Backup löschen */
export const deleteBackupArchive = (name) => apiDelete(`/api/backup/archives/${encodeURIComponent(name)}`);

/** POST /api/backup/restore – Backup wiederherstellen (DB + PDFs) */
export const restoreBackup = (name) => apiPost('/api/backup/restore', { name });

/** GET /api/backup/restore-status – Status der letzten/laufenden Wiederherstellung */
export const getRestoreStatus = () => apiGet('/api/backup/restore-status');

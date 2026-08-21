import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

export const listScanners = () => apiGet('/api/scanners');

export const createScanner = ({ device_key, name, enabled = true, recipient_user_ids = [] }) =>
  apiPost('/api/scanners', { device_key, name, enabled, recipient_user_ids });

export const updateScanner = (id, payload) =>
  apiPatch(`/api/scanners/${encodeURIComponent(String(id))}`, payload);

export const configureScanner = (id, payload) =>
  apiPost(`/api/scanners/${encodeURIComponent(String(id))}/configure`, payload);

export const removeScannerConfiguration = (id) =>
  apiDelete(`/api/scanners/${encodeURIComponent(String(id))}/configuration`);

// command: 'page' (Seite scannen) | 'finish' (Batch abschließen)
export const triggerScan = (id, command) =>
  apiPost(`/api/scanners/${encodeURIComponent(String(id))}/scan`, { command });

export const cancelScan = (id) =>
  apiPost(`/api/scanners/${encodeURIComponent(String(id))}/cancel`, {});

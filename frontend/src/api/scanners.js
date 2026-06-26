import { apiGet, apiPatch, apiPost } from './client.js';

export const listScanners = () => apiGet('/api/scanners');

export const createScanner = ({ device_key, name, enabled = true, recipient_user_ids = [] }) =>
  apiPost('/api/scanners', { device_key, name, enabled, recipient_user_ids });

export const updateScanner = (id, payload) =>
  apiPatch(`/api/scanners/${encodeURIComponent(String(id))}`, payload);

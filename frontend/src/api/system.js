import { apiGet, apiPost } from './client.js';

/** GET /api/system/status – Hardware-/Systemstatus des Hosts (Raspberry Pi) */
export const getSystemStatus = () => apiGet('/api/system/status');

/** GET /api/system/services – Status der PaperMind-Dienste */
export const getServiceStatus = () => apiGet('/api/system/services');

/** POST /api/system/services/{service}/actions/{action} – Dienst testen/steuern */
export const runServiceAction = (serviceKey, action) =>
  apiPost(`/api/system/services/${encodeURIComponent(serviceKey)}/actions/${encodeURIComponent(action)}`, {});

/** POST /api/system/power – Host herunterfahren ("poweroff") oder neu starten ("reboot") */
export const triggerPowerAction = (action) => apiPost('/api/system/power', { action });

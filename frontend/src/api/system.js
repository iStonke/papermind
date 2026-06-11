import { apiGet, apiPost } from './client.js';

/** GET /api/system/status – Hardware-/Systemstatus des Hosts (Raspberry Pi) */
export const getSystemStatus = () => apiGet('/api/system/status');

/** POST /api/system/power – Host herunterfahren ("poweroff") oder neu starten ("reboot") */
export const triggerPowerAction = (action) => apiPost('/api/system/power', { action });

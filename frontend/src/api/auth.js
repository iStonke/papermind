import { apiDelete, apiFetch, apiGet, apiPatch, apiPost, authedUrl, getBaseUrl } from './client.js';

const AUTH_BOOTSTRAP_TIMEOUT_MS = 10_000;

/** POST /api/auth/login – Anmeldung, liefert Token + Benutzer. */
export const login = (username, password) =>
  apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
    handleUnauthorized: false,
    timeoutMs: AUTH_BOOTSTRAP_TIMEOUT_MS,
  });

export const register = ({ username, password, display_name, email }) =>
  apiFetch('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, display_name, email }),
    handleUnauthorized: false,
    timeoutMs: AUTH_BOOTSTRAP_TIMEOUT_MS,
  });

export const refreshSession = (refreshToken) =>
  apiFetch('/api/auth/refresh', {
    method: 'POST',
    body: JSON.stringify(refreshToken ? { refresh_token: refreshToken } : {}),
    handleUnauthorized: false,
    timeoutMs: AUTH_BOOTSTRAP_TIMEOUT_MS,
  });

export const renewSession = () =>
  apiFetch('/api/auth/renew', {
    method: 'POST',
    body: JSON.stringify({}),
    handleUnauthorized: false,
    timeoutMs: AUTH_BOOTSTRAP_TIMEOUT_MS,
  });

/** GET /api/auth/me – aktueller Benutzer (validiert das Token). */
export const fetchCurrentUser = () => apiGet('/api/auth/me');

/** GET /api/auth/file-token – kurzlebiges, datei-scoped Token für Bild-/PDF-/Download-URLs. */
export const fetchFileToken = () => apiFetch('/api/auth/file-token', {
  timeoutMs: AUTH_BOOTSTRAP_TIMEOUT_MS,
});

/** PATCH /api/auth/me – eigenes Profil aktualisieren (Anzeigename, E-Mail, Benutzername).
 * Nur gesetzte Felder mitsenden (undefined = unverändert). */
export const updateProfile = (fields) => {
  const body = {};
  if (fields.username !== undefined) body.username = fields.username;
  if (fields.display_name !== undefined) body.display_name = fields.display_name;
  if (fields.email !== undefined) body.email = fields.email;
  return apiPatch('/api/auth/me', body);
};

/** GET /api/auth/sessions – aktive Sitzungen des aktuellen Benutzers. */
export const listSessions = () => apiGet('/api/auth/sessions');

/** DELETE /api/auth/sessions/{id} – eine einzelne Sitzung widerrufen. */
export const revokeSession = (sessionId) =>
  apiDelete(`/api/auth/sessions/${sessionId}`);

/** POST /api/auth/sessions/revoke-others – alle anderen Sitzungen abmelden. */
export const revokeOtherSessions = () =>
  apiPost('/api/auth/sessions/revoke-others', {});

/** POST /api/auth/change-password – eigenes Passwort ändern. */
export const changePassword = (currentPassword, newPassword) =>
  apiPost('/api/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });

/** POST /api/auth/me/avatar – Profilbild hochladen/ersetzen (multipart). */
export const uploadAvatar = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return apiFetch('/api/auth/me/avatar', { method: 'POST', body: fd });
};

/** DELETE /api/auth/me/avatar – Profilbild entfernen. */
export const deleteAvatar = () =>
  apiFetch('/api/auth/me/avatar', { method: 'DELETE' });

/** GET /api/auth/me/storage – owner-scoped Speicherbelegung (Summe + je Rolle). */
export const fetchStorageUsage = () => apiGet('/api/auth/me/storage');

/** Download-URL für den persönlichen Komplett-Export (ZIP, alle eigenen Dokumente + Metadaten).
 * Nur URL-Builder – der Download läuft über ein natives <a download> mit File-Token. */
export const personalExportUrl = () =>
  authedUrl(`${getBaseUrl()}/api/auth/me/export`);

/** DELETE /api/auth/me – eigenes Konto löschen (nur Nicht-Admins, Passwort bestätigt). */
export const deleteAccount = (password) =>
  apiFetch('/api/auth/me', { method: 'DELETE', body: JSON.stringify({ password }) });

/** POST /api/auth/logout – widerruft nur die aktuelle Geräte-Session. */
export const logout = () => apiPost('/api/auth/logout', {});

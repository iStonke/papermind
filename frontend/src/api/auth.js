import { apiFetch, apiGet, apiPatch, apiPost } from './client.js';

/** POST /api/auth/login – Anmeldung, liefert Token + Benutzer. */
export const login = (username, password) =>
  apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
    handleUnauthorized: false,
  });

export const refreshSession = (refreshToken) =>
  apiFetch('/api/auth/refresh', {
    method: 'POST',
    body: JSON.stringify(refreshToken ? { refresh_token: refreshToken } : {}),
    handleUnauthorized: false,
  });

export const renewSession = () =>
  apiFetch('/api/auth/renew', {
    method: 'POST',
    body: JSON.stringify({}),
    handleUnauthorized: false,
  });

/** GET /api/auth/me – aktueller Benutzer (validiert das Token). */
export const fetchCurrentUser = () => apiGet('/api/auth/me');

/** GET /api/auth/file-token – kurzlebiges, datei-scoped Token für Bild-/PDF-/Download-URLs. */
export const fetchFileToken = () => apiGet('/api/auth/file-token');

/** PATCH /api/auth/me – eigenes Profil aktualisieren (Anzeigename, E-Mail). */
export const updateProfile = ({ display_name, email }) =>
  apiPatch('/api/auth/me', { display_name, email });

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

/** POST /api/auth/logout – widerruft nur die aktuelle Geräte-Session. */
export const logout = () => apiPost('/api/auth/logout', {});

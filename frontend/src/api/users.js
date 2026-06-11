import { apiDelete, apiGet, apiPatch, apiPost } from './client.js';

/** GET /api/users – alle Benutzer (nur Admin). */
export const listUsers = () => apiGet('/api/users');

/** POST /api/users – Benutzer anlegen (nur Admin). */
export const createUser = ({ username, password, display_name = null, email = null, is_admin = false }) =>
  apiPost('/api/users', { username, password, display_name, email, is_admin });

/** PATCH /api/users/{id} – Benutzer aktualisieren (nur Admin). */
export const updateUser = (id, payload) =>
  apiPatch(`/api/users/${id}`, payload);

/** DELETE /api/users/{id} – Benutzer löschen (nur Admin). */
export const deleteUser = (id) => apiDelete(`/api/users/${id}`);

/**
 * Zentraler API-Client für PaperMind.
 *
 * Alle Requests laufen über apiFetch(). Die Methoden-Helfer
 * (apiGet, apiPost, apiPatch, apiPut, apiDelete) decken die
 * gängigen Fälle ab.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

/**
 * Liest die Fehlermeldung aus einer nicht-ok Response.
 * Versucht JSON zu parsen, fällt auf Status-Text zurück.
 */
async function readErrorMessage(response) {
  try {
    const payload = await response.json();
    return payload?.error?.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

/**
 * Basis-Fetch. Wirft bei !response.ok einen Error mit der
 * API-Fehlermeldung. Gibt null zurück bei 204 No Content.
 *
 * @param {string} path  - Pfad ab der Base-URL, z.B. "/api/documents"
 * @param {RequestInit} options - Standard fetch-Optionen
 * @returns {Promise<any>}
 */
export async function apiFetch(path, options = {}) {
  const headers = { ...options.headers };
  if (options.body && typeof options.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (response.status === 204) return null;
  return response.json();
}

/** GET  /api/... */
export const apiGet = (path) => apiFetch(path);

/** POST /api/... mit JSON-Body */
export const apiPost = (path, body) =>
  apiFetch(path, { method: 'POST', body: JSON.stringify(body) });

/** PATCH /api/... mit JSON-Body */
export const apiPatch = (path, body) =>
  apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) });

/** PUT /api/... mit JSON-Body */
export const apiPut = (path, body) =>
  apiFetch(path, { method: 'PUT', body: JSON.stringify(body) });

/** DELETE /api/... */
export const apiDelete = (path) =>
  apiFetch(path, { method: 'DELETE' });

/** Gibt die konfigurierte Base-URL zurück (z.B. für bestehende API-Module). */
export const getBaseUrl = () => BASE_URL;

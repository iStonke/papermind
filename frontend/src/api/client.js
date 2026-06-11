/**
 * Zentraler API-Client für PaperMind.
 *
 * Alle Requests laufen über apiFetch(). Die Methoden-Helfer
 * (apiGet, apiPost, apiPatch, apiPut, apiDelete) decken die
 * gängigen Fälle ab.
 *
 * Authentifizierung: Das Access-Token wird in localStorage gehalten und
 * automatisch als `Authorization: Bearer`-Header an jeden Request gehängt.
 * Bei einer 401-Antwort wird das Token verworfen und ein registrierter
 * Handler benachrichtigt (zeigt den Login-Screen).
 */

import { API_BASE_URL } from './config.js';

const BASE_URL = API_BASE_URL;
const TOKEN_KEY = 'pm_auth_token';

let unauthorizedHandler = null;

// Kurzlebiges, datei-scoped Token (nur In-Memory) für native Ressourcen-Loads.
// Bewusst NICHT das Session-Token, damit kein langlebiges Token in URLs/Logs landet.
let fileToken = '';

/** Registriert einen Callback, der bei 401-Antworten ausgelöst wird. */
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = typeof fn === 'function' ? fn : null;
}

/** Setzt das aktuelle Datei-Token (vom Auth-Store gepflegt). */
export function setFileToken(token) {
  fileToken = token || '';
}

/** Liest das gespeicherte Access-Token (oder leeren String). */
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

/** Speichert (oder löscht bei falsy) das Access-Token. */
export function setToken(token) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* localStorage nicht verfügbar – ignorieren */
  }
}

/**
 * Hängt das Token als Query-Parameter an eine rohe Ressourcen-URL an.
 * Nötig für native Loads (z. B. <img>, PDF-Viewer, Downloads), die keinen
 * Authorization-Header setzen können.
 */
export function authedUrl(url) {
  if (!fileToken) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(fileToken)}`;
}

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

  const token = getToken();
  if (token && !headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (response.status === 401) {
    setToken(null);
    if (unauthorizedHandler) unauthorizedHandler();
    throw new Error(await readErrorMessage(response));
  }

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (response.status === 204) return null;

  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (!contentType.includes('application/json')) {
    throw new Error('Keine gültige Antwort vom Server.');
  }

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

/** Authorization-Header für manuelle fetch()-Aufrufe. */
export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

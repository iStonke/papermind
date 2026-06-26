/**
 * Zentraler API-Client für PaperMind.
 *
 * Alle Requests laufen über apiFetch(). Die Methoden-Helfer
 * (apiGet, apiPost, apiPatch, apiPut, apiDelete) decken die
 * gängigen Fälle ab.
 *
 * Authentifizierung: Das Access-Token wird nur im Arbeitsspeicher gehalten und
 * automatisch als `Authorization: Bearer`-Header an jeden Request gehängt.
 * Bei einer 401-Antwort wird ein registrierter Handler benachrichtigt. Der
 * Auth-Store versucht zunächst eine Session-Erneuerung und meldet nur ab, wenn
 * auch das Refresh-Token ausdrücklich abgelehnt wird.
 */

import { API_BASE_URL } from './config.js';

const BASE_URL = API_BASE_URL;
const TOKEN_KEY = 'pm_auth_token';
const REFRESH_TOKEN_KEY = 'pm_auth_refresh_token';

let unauthorizedHandler = null;
let accessToken = '';
let legacyRefreshToken = '';

// Einmalige Übernahme bestehender Sessions. Neue Tokens werden nicht mehr in
// Web Storage geschrieben; das Refresh-Token lebt ausschließlich im
// HttpOnly-Cookie.
try {
  accessToken = localStorage.getItem(TOKEN_KEY) || '';
  legacyRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY) || '';
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
} catch {
  /* Web Storage nicht verfügbar */
}

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
  return accessToken;
}

/** Hält das Access-Token nur für die Lebensdauer des aktuellen Tabs. */
export function setToken(token) {
  accessToken = token || '';
}

export function getRefreshToken() {
  return legacyRefreshToken;
}

export function setRefreshToken(token) {
  legacyRefreshToken = token || '';
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

async function responseError(response) {
  const error = new Error(await readErrorMessage(response));
  error.status = response.status;
  return error;
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
  const {
    handleUnauthorized = true,
    timeoutMs = 0,
    ...fetchOptions
  } = options;
  const headers = { ...fetchOptions.headers };
  if (fetchOptions.body && typeof fetchOptions.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }

  const token = getToken();
  if (token && !headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const timeoutController = timeoutMs > 0 ? new AbortController() : null;
  let timeoutHandle = null;
  if (timeoutController) {
    timeoutHandle = setTimeout(() => timeoutController.abort(), timeoutMs);
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      // API-Antworten nie aus dem Browser-Cache bedienen – sonst liefern
      // wiederholte GETs (z. B. das 15s-Polling der Import-Inbox) veraltete
      // Daten und neue Scans erscheinen erst nach einem harten Reload.
      cache: 'no-store',
      credentials: 'include',
      ...fetchOptions,
      signal: timeoutController?.signal || fetchOptions.signal,
      headers,
    });
  } catch (error) {
    if (timeoutController?.signal.aborted) {
      const timeoutError = new Error('Der Server antwortet nicht.');
      timeoutError.code = 'REQUEST_TIMEOUT';
      throw timeoutError;
    }
    throw error;
  } finally {
    if (timeoutHandle) clearTimeout(timeoutHandle);
  }

  if (response.status === 401 && handleUnauthorized) {
    if (unauthorizedHandler) unauthorizedHandler();
    throw await responseError(response);
  }

  if (!response.ok) {
    throw await responseError(response);
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

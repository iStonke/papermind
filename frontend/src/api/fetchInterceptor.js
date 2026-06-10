/**
 * Globaler fetch-Interceptor.
 *
 * Die App setzt an vielen Stellen rohe `fetch()`-Aufrufe gegen die API ab
 * (statt ausschließlich über den apiClient). Damit Authentifizierung überall
 * konsistent greift, hängt dieser Interceptor an JEDEN `/api/`-Request
 * automatisch den `Authorization: Bearer`-Header an und behandelt 401-Antworten
 * zentral (Token verwerfen + Logout-Handler auslösen).
 *
 * Native Ressourcen-Loads (z. B. <img>, PDF-Viewer, window.open-Downloads)
 * laufen NICHT über fetch und tragen das Token stattdessen als Query-Parameter
 * (siehe `authedUrl` im apiClient).
 */

import { getToken, setToken } from './client.js';

let installed = false;
let unauthorizedHandler = null;

export function setFetchUnauthorizedHandler(fn) {
  unauthorizedHandler = typeof fn === 'function' ? fn : null;
}

function targetsApi(url) {
  return typeof url === 'string' && url.includes('/api/');
}

export function installFetchInterceptor() {
  if (installed || typeof window === 'undefined' || !window.fetch) return;
  installed = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input?.url || '';

    if (!targetsApi(url)) {
      return originalFetch(input, init);
    }

    const token = getToken();
    const headers = new Headers(
      init.headers || (typeof input !== 'string' ? input.headers : undefined),
    );
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const nextInit = { ...init, headers };

    const response = await originalFetch(
      typeof input === 'string' ? input : input.url,
      nextInit,
    );

    if (response.status === 401) {
      setToken(null);
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return response;
  };
}

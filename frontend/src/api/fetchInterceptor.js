/**
 * Globaler fetch-Interceptor.
 *
 * Die App setzt an vielen Stellen rohe `fetch()`-Aufrufe gegen die API ab
 * (statt ausschließlich über den apiClient). Damit Authentifizierung überall
 * konsistent greift, hängt dieser Interceptor an JEDEN `/api/`-Request
 * automatisch den `Authorization: Bearer`-Header an und meldet 401-Antworten
 * zentral an den Auth-Store, der zunächst eine Session-Erneuerung versucht.
 *
 * Native Ressourcen-Loads (z. B. <img>, PDF-Viewer, window.open-Downloads)
 * laufen NICHT über fetch und tragen das Token stattdessen als Query-Parameter
 * (siehe `authedUrl` im apiClient).
 *
 * Meldet der Server kurzzeitige Überlast (503 mit `Retry-After`, z. B.
 * DATABASE_BUSY nach einem DB-Sperr-Timeout), wiederholt der Interceptor
 * lesende Requests genau einmal. Schreibende Requests werden nie automatisch
 * wiederholt – ob sie schon gewirkt haben, kann der Client nicht wissen.
 */

import { getToken, targetsApi } from './client.js';
import { apiSessionGeneration, assertApiSession, onApiSessionReset } from './session.js';

let installed = false;
let unauthorizedHandler = null;

const RETRYABLE_METHODS = new Set(['GET', 'HEAD']);
const MAX_BUSY_RETRY_DELAY_MS = 10_000;

/** Wartezeit bis zum einmaligen Wiederholen oder null, wenn nicht wiederholt wird. */
export function busyRetryDelayMs(response, method) {
  if (response?.status !== 503 || !RETRYABLE_METHODS.has(String(method || 'GET').toUpperCase())) return null;
  const raw = response.headers?.get('Retry-After');
  if (raw == null || String(raw).trim() === '') return null;
  const seconds = Number(raw);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return Math.min(seconds * 1000, MAX_BUSY_RETRY_DELAY_MS);
}

function abortReason(signal) {
  return signal.reason ?? new DOMException('The operation was aborted.', 'AbortError');
}

function waitUnlessAborted(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortReason(signal));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(abortReason(signal));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

export function setFetchUnauthorizedHandler(fn) {
  unauthorizedHandler = typeof fn === 'function' ? fn : null;
}

function isAuthBootstrapRequest(url) {
  return url.includes('/api/auth/login') || url.includes('/api/auth/refresh');
}

export function installFetchInterceptor() {
  if (installed || typeof window === 'undefined' || !window.fetch) return;
  installed = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input?.url || '';

    if (!targetsApi(url)) {
      return originalFetch(input, init);
    }

    const generation = apiSessionGeneration();
    const controller = new AbortController();
    const sourceSignal = init.signal || (input instanceof Request ? input.signal : null);
    // The native link stays effective after response headers arrive, including
    // while an AI stream or a large response body is still being read.
    const hasNativeSignalLink = sourceSignal && typeof AbortSignal.any === 'function';
    const signal = hasNativeSignalLink ? AbortSignal.any([controller.signal, sourceSignal]) : controller.signal;
    const abort = () => controller.abort();
    if (sourceSignal?.aborted) abort();
    else sourceSignal?.addEventListener('abort', abort, { once: true });
    const unsubscribe = onApiSessionReset(abort);

    const token = getToken();
    const headers = new Headers(
      init.headers || (typeof input !== 'string' ? input.headers : undefined),
    );
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    const nextInit = { credentials: 'include', ...init, headers, signal };
    const method = init.method || (input instanceof Request ? input.method : 'GET');
    let response;
    try {
      response = await originalFetch(input, nextInit);
      const retryDelay = busyRetryDelayMs(response, method);
      if (retryDelay !== null) {
        // Verbindung der verworfenen Antwort freigeben, bevor erneut gefragt wird.
        await response.body?.cancel().catch(() => {});
        await waitUnlessAborted(retryDelay, signal);
        assertApiSession(generation);
        response = await originalFetch(input, nextInit);
      }
      assertApiSession(generation);
    } catch (error) {
      sourceSignal?.removeEventListener('abort', abort);
      throw error;
    } finally {
      unsubscribe();
      if (hasNativeSignalLink) sourceSignal?.removeEventListener('abort', abort);
    }
    // Headers can arrive before logout, but JSON can arrive afterwards.
    for (const method of ['json', 'text', 'blob', 'arrayBuffer']) {
      const read = response[method].bind(response);
      response[method] = async (...args) => {
        try {
          const value = await read(...args);
          assertApiSession(generation);
          return value;
        } finally {
          sourceSignal?.removeEventListener('abort', abort);
        }
      };
    }
    if (!response.body) sourceSignal?.removeEventListener('abort', abort);

    if (response.status === 401 && !isAuthBootstrapRequest(url)) {
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return response;
  };
}

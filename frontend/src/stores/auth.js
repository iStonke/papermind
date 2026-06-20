import { defineStore } from 'pinia';

import {
  fetchCurrentUser,
  fetchFileToken,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession as refreshSessionRequest,
  renewSession as renewSessionRequest,
} from '../api/auth.js';
import {
  getRefreshToken,
  getToken,
  setFileToken,
  setRefreshToken,
  setToken,
  setUnauthorizedHandler,
} from '../api/client.js';
import { setFetchUnauthorizedHandler } from '../api/fetchInterceptor.js';

// Timer-Handle für die Datei-Token-Erneuerung (kein reaktiver State).
let fileTokenTimer = null;
let sessionRefreshTimer = null;
let initializePromise = null;
let recoveryPromise = null;

// Inaktivitäts-Logout: Timer + Activity-Listener (kein reaktiver State).
let inactivityTimer = null;
let inactivityResetFn = null;
const AUTO_LOGOUT_KEY = 'pm.autoLogoutMinutes';
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'mousemove', 'wheel', 'touchstart', 'scroll'];

function readAutoLogoutMinutes() {
  if (typeof window === 'undefined') return 0;
  const raw = Number(window.localStorage.getItem(AUTO_LOGOUT_KEY));
  return Number.isFinite(raw) && raw > 0 ? raw : 0;
}

function tokenExpiryMs(token) {
  try {
    const payloadPart = String(token || '').split('.', 1)[0];
    const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
    const payload = JSON.parse(window.atob(normalized + padding));
    return Number(payload?.exp || 0) * 1000;
  } catch {
    return 0;
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    /** 'unknown' bis die Session geprüft wurde, dann true/false. */
    status: 'unknown',
    initializing: false,
    /**
     * Cache-Busting für Avatar-<img>: Der Dateiname pro User bleibt gleich,
     * daher wird dieser Zähler bei jeder Änderung neu gesetzt und als
     * ?v=-Parameter an die Avatar-URL gehängt.
     */
    avatarVersion: Date.now(),
    /** Cache-Key für native Datei-URLs, die vom kurzlebigen File-Token abhängen. */
    fileTokenVersion: 0,
    /** Inaktivitäts-Logout in Minuten (0 = aus); persistiert in localStorage. */
    autoLogoutMinutes: readAutoLogoutMinutes(),
  }),

  getters: {
    isAuthenticated: (state) => state.status === 'authenticated' && !!state.user,
    isAdmin: (state) => !!state.user?.is_admin,
    username: (state) => state.user?.username || '',
  },

  actions: {
    /** Einmalig beim App-Start: 401-Handler registrieren und Token prüfen. */
    async initialize() {
      if (initializePromise) return initializePromise;

      this.initializing = true;
      initializePromise = (async () => {
        try {
          setUnauthorizedHandler(() => this.handleUnauthorized());
          setFetchUnauthorizedHandler(() => this.handleUnauthorized());

          const token = getToken();
          if (!token) {
            if (getRefreshToken()) {
              const recovered = await this.recoverSession();
              if (!recovered && this.status !== 'authenticated') this.status = 'anonymous';
            } else {
              this.status = 'anonymous';
            }
            return;
          }
          try {
            this.user = await fetchCurrentUser();
            this.status = 'authenticated';
            if (!getRefreshToken()) {
              const renewed = await renewSessionRequest();
              this.applyTokenResponse(renewed);
            } else {
              this.scheduleSessionRefresh(token);
              void this.refreshFileToken();
              this.startInactivityWatch();
            }
          } catch {
            const recovered = await this.recoverSession();
            if (!recovered) this.clearSession();
          }
        } catch {
          if (!getRefreshToken()) this.clearSession();
          else if (this.status !== 'authenticated') this.status = 'anonymous';
        } finally {
          this.initializing = false;
          initializePromise = null;
        }
      })();

      return initializePromise;
    },

    async login(username, password) {
      const result = await loginRequest(username, password);
      this.applyTokenResponse(result);
      return result.user;
    },

    applyTokenResponse(result) {
      setToken(result.access_token);
      setRefreshToken(result.refresh_token);
      this.user = result.user;
      this.status = 'authenticated';
      this.scheduleSessionRefresh(result.access_token);
      void this.refreshFileToken();
      this.startInactivityWatch();
    },

    async recoverSession() {
      if (recoveryPromise) return recoveryPromise;
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        if (!getToken()) {
          this.clearSession();
          return false;
        }
        recoveryPromise = (async () => {
          try {
            const result = await renewSessionRequest();
            this.applyTokenResponse(result);
            return true;
          } catch (error) {
            if (error?.status === 401) this.clearSession();
            return false;
          } finally {
            recoveryPromise = null;
          }
        })();
        return recoveryPromise;
      }
      recoveryPromise = (async () => {
        try {
          const result = await refreshSessionRequest(refreshToken);
          this.applyTokenResponse(result);
          return true;
        } catch (error) {
          if (error?.status === 401) {
            this.clearSession();
            return false;
          }
          if (sessionRefreshTimer) window.clearTimeout(sessionRefreshTimer);
          sessionRefreshTimer = window.setTimeout(() => {
            void this.recoverSession();
          }, 30_000);
          return this.isAuthenticated;
        } finally {
          recoveryPromise = null;
        }
      })();
      return recoveryPromise;
    },

    scheduleSessionRefresh(token) {
      if (sessionRefreshTimer) window.clearTimeout(sessionRefreshTimer);
      const expiresAt = tokenExpiryMs(token);
      if (!expiresAt) return;
      const refreshInMs = Math.max(30_000, expiresAt - Date.now() - 5 * 60 * 1000);
      sessionRefreshTimer = window.setTimeout(() => {
        void this.recoverSession();
      }, refreshInMs);
    },

    stopSessionRefresh() {
      if (sessionRefreshTimer) {
        window.clearTimeout(sessionRefreshTimer);
        sessionRefreshTimer = null;
      }
    },

    /** Holt ein kurzlebiges Datei-Token und plant die Erneuerung vor Ablauf. */
    async refreshFileToken() {
      try {
        const res = await fetchFileToken();
        setFileToken(res.token);
        this.fileTokenVersion = Date.now();
        if (fileTokenTimer) clearTimeout(fileTokenTimer);
        const refreshInMs = Math.max(30, (res.expires_in || 300) - 30) * 1000;
        fileTokenTimer = setTimeout(() => { this.refreshFileToken(); }, refreshInMs);
      } catch {
        setFileToken('');
        this.fileTokenVersion = Date.now();
        if (fileTokenTimer) clearTimeout(fileTokenTimer);
        if (this.isAuthenticated) {
          fileTokenTimer = setTimeout(() => { this.refreshFileToken(); }, 30_000);
        }
      }
    },

    stopFileToken() {
      if (fileTokenTimer) {
        clearTimeout(fileTokenTimer);
        fileTokenTimer = null;
      }
      setFileToken('');
      this.fileTokenVersion = Date.now();
    },

    async logout() {
      try {
        await logoutRequest();
      } catch {
        /* egal – Token wird lokal verworfen */
      }
      this.clearSession();
    },

    clearSession() {
      this.stopFileToken();
      this.stopSessionRefresh();
      this.stopInactivityWatch();
      setToken(null);
      setRefreshToken(null);
      this.user = null;
      this.status = 'anonymous';
    },

    /** Ersetzt den Nutzer nach Profil-/Avatar-Änderung und bricht den Bild-Cache. */
    setUser(user) {
      this.user = user;
      this.avatarVersion = Date.now();
    },

    /** Wird vom API-Client bei 401 aufgerufen. */
    handleUnauthorized() {
      void this.recoverSession();
    },

    /** Inaktivitäts-Logout-Dauer setzen (Minuten, 0 = aus) und persistieren. */
    setAutoLogoutMinutes(minutes) {
      const value = Number(minutes) > 0 ? Math.round(Number(minutes)) : 0;
      this.autoLogoutMinutes = value;
      if (typeof window !== 'undefined') {
        if (value > 0) window.localStorage.setItem(AUTO_LOGOUT_KEY, String(value));
        else window.localStorage.removeItem(AUTO_LOGOUT_KEY);
      }
      if (this.isAuthenticated) this.startInactivityWatch();
      else this.stopInactivityWatch();
    },

    /** Startet die Leerlauf-Überwachung: nach autoLogoutMinutes ohne Aktivität → Logout. */
    startInactivityWatch() {
      if (typeof window === 'undefined') return;
      this.stopInactivityWatch();
      if (!(this.autoLogoutMinutes > 0)) return;
      const reset = () => {
        if (inactivityTimer) window.clearTimeout(inactivityTimer);
        inactivityTimer = window.setTimeout(() => {
          this.logout();
        }, this.autoLogoutMinutes * 60 * 1000);
      };
      inactivityResetFn = reset;
      for (const ev of ACTIVITY_EVENTS) {
        window.addEventListener(ev, reset, { passive: true });
      }
      reset();
    },

    stopInactivityWatch() {
      if (typeof window === 'undefined') return;
      if (inactivityTimer) {
        window.clearTimeout(inactivityTimer);
        inactivityTimer = null;
      }
      if (inactivityResetFn) {
        for (const ev of ACTIVITY_EVENTS) window.removeEventListener(ev, inactivityResetFn);
        inactivityResetFn = null;
      }
    },
  },
});

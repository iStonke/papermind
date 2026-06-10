import { defineStore } from 'pinia';

import {
  fetchCurrentUser,
  fetchFileToken,
  login as loginRequest,
  logout as logoutRequest,
} from '../api/auth.js';
import { getToken, setFileToken, setToken, setUnauthorizedHandler } from '../api/client.js';
import { setFetchUnauthorizedHandler } from '../api/fetchInterceptor.js';

// Timer-Handle für die Datei-Token-Erneuerung (kein reaktiver State).
let fileTokenTimer = null;

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
  }),

  getters: {
    isAuthenticated: (state) => state.status === 'authenticated' && !!state.user,
    isAdmin: (state) => !!state.user?.is_admin,
    username: (state) => state.user?.username || '',
  },

  actions: {
    /** Einmalig beim App-Start: 401-Handler registrieren und Token prüfen. */
    async initialize() {
      if (this.initializing) return;
      this.initializing = true;
      setUnauthorizedHandler(() => this.handleUnauthorized());
      setFetchUnauthorizedHandler(() => this.handleUnauthorized());

      const token = getToken();
      if (!token) {
        this.status = 'anonymous';
        this.initializing = false;
        return;
      }
      try {
        this.user = await fetchCurrentUser();
        this.status = 'authenticated';
        await this.refreshFileToken();
      } catch {
        this.user = null;
        this.status = 'anonymous';
        setToken(null);
      } finally {
        this.initializing = false;
      }
    },

    async login(username, password) {
      const result = await loginRequest(username, password);
      setToken(result.access_token);
      this.user = result.user;
      this.status = 'authenticated';
      await this.refreshFileToken();
      return result.user;
    },

    /** Holt ein kurzlebiges Datei-Token und plant die Erneuerung vor Ablauf. */
    async refreshFileToken() {
      try {
        const res = await fetchFileToken();
        setFileToken(res.token);
        if (fileTokenTimer) clearTimeout(fileTokenTimer);
        const refreshInMs = Math.max(30, (res.expires_in || 300) - 30) * 1000;
        fileTokenTimer = setTimeout(() => { this.refreshFileToken(); }, refreshInMs);
      } catch {
        setFileToken('');
      }
    },

    stopFileToken() {
      if (fileTokenTimer) {
        clearTimeout(fileTokenTimer);
        fileTokenTimer = null;
      }
      setFileToken('');
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
      setToken(null);
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
      this.stopFileToken();
      this.user = null;
      this.status = 'anonymous';
    },
  },
});

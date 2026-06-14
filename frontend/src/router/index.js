import { createRouter, createWebHistory } from 'vue-router';

import { getToken } from '../api/client.js';
import { useAuthStore } from '../stores/auth.js';

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  {
    // Authentifizierter Bereich: gemeinsame Shell (v-app + globaler
    // SettingsDialog + Theme-Bootstrap) bleibt über alle Kind-Routen gemountet.
    path: '/',
    component: () => import('../views/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'documents',
        component: () => import('../views/DocumentsView.vue'),
      },
    ],
  },
  // Fallback: alles Unbekannte zur Startseite.
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.onError((error) => {
  const message = String(error?.message || error || '');
  const isChunkLoadError =
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('error loading dynamically imported module');

  if (!isChunkLoadError || typeof window === 'undefined') {
    return;
  }

  const reloadKey = 'pm.router.dynamic-import-reload';
  if (window.sessionStorage.getItem(reloadKey) === '1') {
    window.sessionStorage.removeItem(reloadKey);
    return;
  }

  window.sessionStorage.setItem(reloadKey, '1');
  window.location.reload();
});

router.afterEach(() => {
  if (typeof window !== 'undefined') {
    window.sessionStorage.removeItem('pm.router.dynamic-import-reload');
  }
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // Beim ersten Navigieren die Session prüfen (idempotent).
  let authCheckDeferred = false;
  if (auth.status === 'unknown') {
    const hasStoredToken = Boolean(getToken());
    if (hasStoredToken && to.meta.requiresAuth) {
      void auth.initialize();
      authCheckDeferred = true;
    } else {
      await auth.initialize();
    }
  }

  // Bereits angemeldet → Login-Seite überspringen.
  if (to.name === 'login') {
    return auth.isAuthenticated ? { path: '/' } : true;
  }

  // Geschützte Routen erfordern eine Anmeldung.
  if (to.meta.requiresAuth && !authCheckDeferred && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }

  return true;
});

export default router;

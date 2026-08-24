import { createRouter, createWebHistory } from 'vue-router';

import { getToken } from '../api/client.js';
import { useAuthStore } from '../stores/auth.js';
import LoginView from '../views/LoginView.vue';
import AppLayout from '../views/AppLayout.vue';
// Route-Komponenten bleiben bewusst STATISCH importiert: dynamische Route-Imports
// haben hier einen Startup-Deadlock verursacht (siehe Commit 24caf70 + Regressions-
// test routerBoot.test.mjs). Bundle-Splitting passiert stattdessen auf
// Komponenten-Ebene (defineAsyncComponent für die schweren Dialoge), was den
// Navigations-Guard nicht blockiert.
import DocumentsView from '../views/DocumentsView.vue';
// DEV-only Editor-Prüfstand (M0). Statisch importiert wie die übrigen Routen
// (dynamische Route-Imports haben den Startup-Guard blockiert); der Prod-Build
// entfernt Route UND Import als Dead Code, da import.meta.env.DEV dort false ist.
import NotesDevHarness from '../views/NotesDevHarness.vue';

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true },
  },
  // DEV-only Prüfstand für den Notizen-Editor (M0). Öffentlich & ohne Auth,
  // damit die Schreibfläche isoliert auf 127.0.0.1:5179 geprüft werden kann.
  // Wird im Prod-Build nicht registriert.
  ...(import.meta.env.DEV
    ? [{
        path: '/dev/notes',
        name: 'dev-notes',
        component: NotesDevHarness,
        meta: { public: true },
      }]
    : []),
  {
    // Authentifizierter Bereich: gemeinsame Shell (v-app + globaler
    // SettingsDialog + Theme-Bootstrap) bleibt über alle Kind-Routen gemountet.
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'documents',
        component: DocumentsView,
      },
      {
        path: 'tische',
        name: 'dossiers',
        component: DocumentsView,
      },
      {
        path: 'tische/:dossierId',
        name: 'dossier-board',
        component: DocumentsView,
      },
      {
        path: 'wissen',
        name: 'wiki',
        component: DocumentsView,
      },
      // Alt-Pfade (vor der „Leuchttisch"-Umbenennung) umleiten – Query bleibt erhalten.
      {
        path: 'akten',
        redirect: (to) => ({ name: 'dossiers', query: to.query }),
      },
      {
        path: 'akten/:dossierId',
        redirect: (to) => ({ name: 'dossier-board', params: { dossierId: to.params.dossierId }, query: to.query }),
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

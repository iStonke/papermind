import { createRouter, createWebHistory } from 'vue-router';

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

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // Beim ersten Navigieren die Session prüfen (idempotent).
  if (auth.status === 'unknown') {
    await auth.initialize();
  }

  // Bereits angemeldet → Login-Seite überspringen.
  if (to.name === 'login') {
    return auth.isAuthenticated ? { path: '/' } : true;
  }

  // Geschützte Routen erfordern eine Anmeldung.
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }

  return true;
});

export default router;

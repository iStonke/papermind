import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import MobileScanCaptureView from './views/mobile/MobileScanCaptureView.vue';
import MobileUploadView from './views/mobile/MobileUploadView.vue';
import vuetify from './plugins/vuetify';
import './style.css';
import './theme/theme.css';

if (typeof Promise.withResolvers !== 'function') {
  Promise.withResolvers = function withResolvers() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

function resolveMobileRoute() {
  if (typeof window === 'undefined') {
    return null;
  }
  const query = new URLSearchParams(window.location.search);

  const scanMatch = window.location.pathname.match(/^\/m\/scan\/?$/);
  if (scanMatch) {
    const token = String(query.get('token') || query.get('t') || '').trim();
    return { kind: 'scan', token };
  }

  const uploadMatch = window.location.pathname.match(/^\/m\/upload\/([^/]+)\/?$/);
  if (uploadMatch) {
    const sessionId = decodeURIComponent(uploadMatch[1] || '').trim();
    if (!sessionId) {
      return null;
    }
    const token = String(query.get('t') || '').trim();
    return { kind: 'upload-legacy', sessionId, token };
  }

  return null;
}

function isLocalHostName(hostname = '') {
  const normalized = String(hostname || '').trim().toLowerCase();
  return normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '::1' || normalized === '[::1]';
}

function resolveMobileApiBaseUrl() {
  const fromEnv = String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
  if (!fromEnv || typeof window === 'undefined') {
    return fromEnv;
  }

  try {
    const envUrl = new URL(fromEnv);
    const currentHost = String(window.location.hostname || '');
    if (!isLocalHostName(currentHost) && isLocalHostName(envUrl.hostname)) {
      return '';
    }
  } catch {
    // ignore parse errors and keep env value
  }

  return fromEnv;
}

const mobileRoute = resolveMobileRoute();
let app = createApp(App);
if (mobileRoute?.kind === 'scan') {
  app = createApp(MobileScanCaptureView, {
    initialToken: mobileRoute.token,
    apiBaseUrl: resolveMobileApiBaseUrl()
  });
} else if (mobileRoute?.kind === 'upload-legacy') {
  app = createApp(MobileUploadView, {
    sessionId: mobileRoute.sessionId,
    initialToken: mobileRoute.token,
    apiBaseUrl: resolveMobileApiBaseUrl()
  });
}

app.use(createPinia()).use(vuetify).mount('#app');

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import MobileUploadView from './views/mobile/MobileUploadView.vue';
import vuetify from './plugins/vuetify';
import './style.css';

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
  const match = window.location.pathname.match(/^\/m\/upload\/([^/]+)\/?$/);
  if (!match) {
    return null;
  }
  const sessionId = decodeURIComponent(match[1] || '').trim();
  if (!sessionId) {
    return null;
  }
  const token = new URLSearchParams(window.location.search).get('t') || '';
  return { sessionId, token };
}

const mobileRoute = resolveMobileRoute();
const app = mobileRoute
  ? createApp(MobileUploadView, {
    sessionId: mobileRoute.sessionId,
    initialToken: mobileRoute.token,
    apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  })
  : createApp(App);

app.use(createPinia()).use(vuetify).mount('#app');

import { createApp } from 'vue';
import { createPinia } from 'pinia';
import AppRoot from './AppRoot.vue';
import router from './router';
import vuetify from './plugins/vuetify';
import { installFetchInterceptor } from './api/fetchInterceptor.js';
import './style.css';
import './theme/theme.css';

installFetchInterceptor();

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

const app = createApp(AppRoot);
app.use(createPinia()).use(router).use(vuetify).mount('#app');

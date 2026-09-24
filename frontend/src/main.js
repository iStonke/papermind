import { createApp } from 'vue';
import { createPinia } from 'pinia';
import AppRoot from './AppRoot.vue';
import router from './router';
import vuetify from './plugins/vuetify';
import { installFetchInterceptor } from './api/fetchInterceptor.js';
import '@fontsource-variable/inter/wght.css';
import '@fontsource-variable/inter/wght-italic.css';
import '@fontsource-variable/source-sans-3/wght.css';
import '@fontsource-variable/source-sans-3/wght-italic.css';
import '@fontsource-variable/atkinson-hyperlegible-next/wght.css';
import '@fontsource-variable/atkinson-hyperlegible-next/wght-italic.css';
import '@fontsource-variable/source-serif-4/wght.css';
import '@fontsource-variable/source-serif-4/wght-italic.css';
import './style.css';
import './theme/theme.css';
import './theme/searchbar.css';
import './theme/lists.css';

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

import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import SettingsDialog from '../../../src/components/SettingsDialog.vue';
import { useAuthStore } from '../../../src/stores/auth.js';
import { useSettingsStore } from '../../../src/stores/settings.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export async function mount({ theme = 'light' } = {}) {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'document-details-test', username: 'test', is_admin: false };
  const store = useSettingsStore(pinia);
  await store.fetchSettings('');
  vuetify.theme.global.name.value = theme;
  document.querySelector('#app').classList.add('papermind-app', `v-theme--${theme}`);
  document.querySelector('#app').dataset.theme = theme;
  const app = createApp({ render: () => h(SettingsDialog, { modelValue: true, initialCategory: 'document_details' }) }).use(pinia).use(vuetify);
  app.mount('#app');
  window.documentSettings = store;
  window.unmountDocumentSettings = () => app.unmount();
}

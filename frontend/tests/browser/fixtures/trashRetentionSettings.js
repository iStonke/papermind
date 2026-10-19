import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import SettingsDialog from '../../../src/components/SettingsDialog.vue';
import { useAuthStore } from '../../../src/stores/auth.js';
import { useSettingsStore } from '../../../src/stores/settings.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export async function mountTrashRetentionSettings({ admin = true } = {}) {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'trash-settings-test', username: 'test', is_admin: admin };
  await useSettingsStore(pinia).fetchSettings('');
  const app = createApp({
    render: () => h(SettingsDialog, { modelValue: true, initialCategory: 'general' }),
  }).use(pinia).use(vuetify);
  app.mount('#app');
  window.unmountTrashRetentionSettings = () => app.unmount();
}

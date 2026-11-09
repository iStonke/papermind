import { createApp, h, reactive } from 'vue';
import { createPinia } from 'pinia';
import SettingsDialog from '../../../src/components/SettingsDialog.vue';
import { useSettingsStore } from '../../../src/stores/settings.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export function mountVocabularySettings({ dark = false, category = 'categories' } = {}) {
  const pinia = createPinia();
  useSettingsStore(pinia).applySettingsFromBackend({ ui: { theme_mode: dark ? 'dark' : 'light' } });
  useSettingsStore(pinia).setAnimationsEnabled(true);
  const root = reactive({ open: true });
  vuetify.theme.global.name.value = dark ? 'dark' : 'light';
  const app = createApp({ render: () => h(SettingsDialog, {
    modelValue: root.open, initialCategory: category, 'onUpdate:modelValue': value => root.open = value,
  }) }).use(pinia).use(vuetify);
  app.mount('#app');
}

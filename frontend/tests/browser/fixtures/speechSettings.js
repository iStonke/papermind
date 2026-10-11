import { createApp, h, reactive } from 'vue';
import { createPinia } from 'pinia';
import SettingsDialog from '../../../src/components/SettingsDialog.vue';
import NoteSpeechSettings from '../../../src/components/notes/NoteSpeechSettings.vue';
import { useSettingsStore } from '../../../src/stores/settings.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/workspaces/documents/workspace.css';

export function mountSpeechSettings({ full = true, initial = {}, dark = false } = {}) {
  const pinia = createPinia();
  const store = useSettingsStore(pinia);
  store.applySettingsFromBackend({ ui: initial });
  const root = reactive({ open: true });
  vuetify.theme.global.name.value = dark ? 'dark' : 'light';
  const app = createApp({ render: () => full
    ? h(SettingsDialog, { modelValue: root.open, initialCategory: 'notes_speech', 'onUpdate:modelValue': value => root.open = value })
    : h(NoteSpeechSettings, { ui: store.settingsDraft.ui, saving: store.isSettingSaving,
      onChange: async ({ key, value }) => { store.setDraftPatch({ ui: { [key]: value } }); await store.saveSettingPatch('', { controlKey: key, patch: { ui: { [key]: value } } }); } }),
  }).use(pinia).use(vuetify);
  app.mount('#app');
  window.speechSettingsStore = store;
  window.unmountSpeechSettings = () => app.unmount();
}

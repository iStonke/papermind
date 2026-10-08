import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import ThoughtsWorkspace from '../../../src/views/ThoughtsWorkspace.vue';
import { useAuthStore } from '../../../src/stores/auth.js';
import { useNotesStore } from '../../../src/stores/notes.js';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';

export function mountThoughts() {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'summary-test', username: 'test' };
  window.thoughtsNotesStore = useNotesStore(pinia);
  window.openedNote = null;
  const app = createApp({ render: () => h(ThoughtsWorkspace, { onOpenNote: id => { window.openedNote = id; } }) });
  app.use(pinia).use(vuetify).mount('#app');
  window.thoughtSummaryFixture = app;
  window.setThoughtsTheme = name => {
    vuetify.theme.global.name.value = name;
    document.querySelector('#app').classList.toggle('v-theme--dark', name === 'dark');
    document.querySelector('#app').classList.toggle('v-theme--light', name !== 'dark');
  };
}

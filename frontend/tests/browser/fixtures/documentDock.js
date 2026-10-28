import { createApp } from 'vue';
import vuetify from '../../../src/plugins/vuetify.js';
import 'vuetify/styles';
import '../../../src/style.css';
import '../../../src/theme/theme.css';
import '../../../src/theme/lists.css';
import '../../../src/workspaces/documents/workspace.css';
import DocumentDock from './DocumentDock.vue';
export function mount() {
  const app = createApp(DocumentDock);
  app.use(vuetify);
  vuetify.theme.global.name.value = 'dark';
  window.dock = app.mount('#app');
}

import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import { useNotesStore } from '../../../src/stores/notes.js';
import Vorlagenmappe from '../../../src/components/notes/Vorlagenmappe.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountBuiltinTemplates() {
  const pinia = createPinia();
  const store = useNotesStore(pinia);
  store.activeCollectionId = 'collection';
  store.templatesLoaded = store.blockTemplatesLoaded = true;
  store.templates.push({ id: 'custom', title: 'Eigene Startnotiz' });
  window.templateStore = store;
  createApp({ render: () => h(Vorlagenmappe, { onOpenNote: id => { window.openedTemplateNote = id; } }) }).use(pinia).use(vuetify).mount('#app');
}

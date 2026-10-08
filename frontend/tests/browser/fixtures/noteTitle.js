import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import { useAuthStore } from '../../../src/stores/auth.js';
import NoteWorkspaceEditor from '../../../src/components/notes/NoteWorkspaceEditor.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountTitleEditor() {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'title-test', username: 'test' };
  createApp({ render: () => h(NoteWorkspaceEditor, { noteId: 'title-note' }) }).use(pinia).use(vuetify).mount('#app');
}

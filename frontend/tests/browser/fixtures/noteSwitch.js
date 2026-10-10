import { createApp, h, ref } from 'vue';
import { createPinia } from 'pinia';
import { useAuthStore } from '../../../src/stores/auth.js';
import NoteWorkspaceEditor from '../../../src/components/notes/NoteWorkspaceEditor.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountSwitch() {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'switch-test', username: 'test' };
  const noteId = ref('lecture-note');
  window.switchNote = (id) => { noteId.value = id; };
  createApp({ render: () => h(NoteWorkspaceEditor, { noteId: noteId.value }) }).use(pinia).use(vuetify).mount('#app');
}

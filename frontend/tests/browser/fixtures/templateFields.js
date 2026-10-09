import { createApp, h, ref } from 'vue';
import { createPinia } from 'pinia';
import { useAuthStore } from '../../../src/stores/auth.js';
import NoteEditor from '../../../src/components/notes/NoteEditor.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';
export function mountTemplateFields() {
  const pinia = createPinia();
  useAuthStore(pinia).user = { id: 'lecture-test', username: 'test' };
  const body = ref({ type: 'doc', content: [{ type: 'templateBox', attrs: { title: 'Vorlesung', color: 'rose' }, content: ['Titel', 'Datum', 'Thema', 'Klausurrelevanz'].map(label => ({ type: 'templateField', attrs: { label, hint: 'Meetingbezeichnung' } })) }] });
  window.lectureBody = body.value;
  createApp({ render: () => h(NoteEditor, {
    noteId: 'lecture-note', workspace: true, modelValue: body.value,
    'onUpdate:modelValue': value => { body.value = value; window.lectureBody = value; },
  }) }).use(pinia).use(vuetify).mount('#app');
}

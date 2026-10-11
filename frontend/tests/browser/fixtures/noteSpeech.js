import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import NoteEditor from '../../../src/components/notes/NoteEditor.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';

export function mountSpeechEditor({ paragraphs = ['Dieser Text wird vorgelesen.'] } = {}) {
  const app = createApp({ render: () => h(NoteEditor, {
    workspace: true,
    modelValue: { type: 'doc', content: paragraphs.map(text => ({ type: 'paragraph', content: [{ type: 'text', text }] })) },
  }) }).use(createPinia()).use(vuetify);
  app.mount('#app');
  window.unmountSpeechEditor = () => app.unmount();
}

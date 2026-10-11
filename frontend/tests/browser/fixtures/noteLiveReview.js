import { createApp, h, shallowRef, reactive, onMounted } from 'vue';
import { Editor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { NoteReviewDecorations } from '../../../src/components/notes/extensions/reviewDecorations.js';
import { useNoteReview } from '../../../src/components/notes/composables/useNoteReview.js';
import { createNoteOverlayCoordinator } from '../../../src/components/notes/composables/noteOverlayCoordinator.js';
import NoteReviewPanel from '../../../src/components/notes/NoteReviewPanel.vue';
import vuetify from '../../../src/plugins/vuetify.js';
import '../../../src/theme/theme.css';

export function mountLiveReview({ invalidAnchor = false } = {}) {
  window.liveCalls = [];
  window.invalidLiveAnchor = invalidAnchor;
  const app = createApp({ setup() {
    const editor = shallowRef(new Editor({ extensions: [StarterKit, NoteReviewDecorations],
      content: '<p>Das Ergebniss steht fest.</p><p>Weitere Notizen</p>' }));
    const c = useNoteReview({ editor, props: reactive({ noteId: 'live', aiAvailable: true }),
      overlays: createNoteOverlayCoordinator(), onCheckpoint() {},
      stream: async (payload, { onEvent, signal }) => {
        const call = { payload, signal };
        window.liveCalls.push(call);
        await new Promise(resolve => { call.finish = resolve; });
        const changes = window.invalidLiveAnchor
          ? [{ id: 1, cat: 'fix', anchor: 'Beispielwort', revised: 'Beispiel', summary: 'Beispiel korrigieren.' }]
          : payload.note_text.includes('Ergebniss') ? [{ id: 1, cat: 'fix', anchor: 'Ergebniss', revised: 'Ergebnis', summary: '„Ergebniss“ durch „Ergebnis“ ersetzen.' }] : [];
        onEvent({ type: 'delta', text: JSON.stringify({ changes }) });
      },
    });
    window.liveReview = { c, editor: editor.value, unmount: () => { app.unmount(); editor.value.destroy(); } };
    onMounted(() => c.startReview());
    return () => h('div', { style: 'display:flex;height:720px;gap:28px;padding:20px' }, [
      h(EditorContent, { editor: editor.value, style: 'width:500px;padding:18px;border:1px solid #d8dfe1' }),
      h('div', { style: 'width:360px;flex:none' }, [h(NoteReviewPanel, { controller: c })]),
    ]);
  } }).use(vuetify);
  app.mount('#app');
}

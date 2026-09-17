import { createApp, h, shallowRef } from 'vue';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { createVuetify } from 'vuetify';
import NoteWritingPrompt from '../../../src/components/notes/NoteWritingPrompt.vue';
import { useNoteWriting } from '../../../src/components/notes/composables/useNoteWriting.js';
import { createNoteOverlayCoordinator } from '../../../src/components/notes/composables/noteOverlayCoordinator.js';

export function mountWritingPlacement() {
  const surface = document.createElement('div');
  surface.id = 'surface';
  surface.style.cssText = 'position:relative;margin-top:440px;height:130px;overflow:hidden';
  document.querySelector('.papermind-app').append(surface);
  const editor = new Editor({
    element: surface, extensions: [StarterKit],
    content: '<p>Hier schreiben</p>' + '<p>Weiterer Absatz</p>'.repeat(30),
  });
  createApp({
    setup() {
      const writing = useNoteWriting({
        editor: shallowRef(editor), surfaceEl: shallowRef(surface),
        props: { noteId: 'placement' }, overlays: createNoteOverlayCoordinator(),
        clampMenuLeft: (left) => left, onCheckpoint() {},
      });
      window.writing = writing;
      writing.openAIPrompt();
      return () => h(NoteWritingPrompt, { controller: writing });
    },
  }).use(createVuetify()).mount('#app');
}

import { createApp, h } from 'vue';
import { Editor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { createVuetify } from 'vuetify';
import { OcrQuote } from '../../../src/components/notes/nodes/ocrQuote.js';
import { EmptyParagraphDeletion } from '../../../src/components/notes/nodes/emptyParagraphDeletion.js';
export function mountQuoteSelection() {
  const editor = new Editor({ extensions: [StarterKit.configure({ trailingNode: false }), OcrQuote, EmptyParagraphDeletion], content: { type: 'doc', content: [
    { type: 'ocrQuote', attrs: { text: 'Dieser Text ist auswählbar und kopierbar.', docTitle: 'Beispiel.pdf' } },
    { type: 'paragraph' },
  ] } });
  window.quoteTestEditor = editor;
  createApp({ render: () => h(EditorContent, { editor }) }).use(createVuetify()).mount('#app');
}

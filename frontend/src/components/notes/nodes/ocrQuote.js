/*
 * ocrQuote — Zitatblock aus einer Beleg-Markierung. Atom-Block; der
 * übernommene OCR-Text und der Anker (Seite/BBox) liegen in Attributen. In M4
 * wird der Anker aus einer echten Konva-Markierung befüllt und klickbar.
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import OcrQuoteView from './OcrQuoteView.vue';

export const OcrQuote = Node.create({
  name: 'ocrQuote',
  group: 'block',
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      text: { default: '' },
      docId: { default: null },
      docTitle: { default: '' },
      page: { default: null },
      // Anker aus der Markierung (Seite + Bounding-Box); in M1 leer.
      bbox: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'blockquote[data-ocr-quote]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['blockquote', mergeAttributes({ 'data-ocr-quote': '' }, HTMLAttributes), HTMLAttributes.text || ''];
  },

  addNodeView() {
    return VueNodeViewRenderer(OcrQuoteView);
  },

  addCommands() {
    return {
      insertOcrQuote: (attrs) => ({ chain }) =>
        chain().insertContent({ type: this.name, attrs }).run(),
    };
  },
});

export default OcrQuote;

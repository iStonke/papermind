import Document from '@tiptap/extension-document';

/**
 * PaperMind-Wurzeldokument mit den bestehenden Notizmetadaten. Layouts sind
 * normale Blockelemente und können frei zwischen anderen Inhalten stehen.
 */
export const PaperMindDocument = Document.extend({
  content: 'block+',

  addAttributes() {
    return {
      favorite: { default: false },
      linkedDocument: { default: null },
      // Mitschrift-Notiz: Folien-Abschnitte (lectureSlide) stehen neben der
      // Mitschrift, eingefügte Screenshots beginnen einen neuen Abschnitt.
      lectureMode: { default: false },
      // side | stacked | text, siehe lectureLayout.js; null = aus lectureMode ableiten.
      lectureLayout: { default: null },
    };
  },
});

export default PaperMindDocument;

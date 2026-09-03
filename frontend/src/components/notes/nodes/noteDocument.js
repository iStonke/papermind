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
    };
  },
});

export default PaperMindDocument;

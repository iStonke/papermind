import { Extension } from '@tiptap/vue-3';

/** Keep provenance on editable blocks without wrapping them in an atomic AI card. */
export const NoteAIGeneration = Extension.create({
  name: 'noteAIGeneration',
  addGlobalAttributes() {
    return [{
      types: ['paragraph', 'heading', 'bulletList', 'orderedList', 'taskList', 'table', 'blockquote', 'codeBlock', 'callout', 'horizontalRule'],
      attributes: { aiGeneration: { default: null, rendered: false } },
    }];
  },
});

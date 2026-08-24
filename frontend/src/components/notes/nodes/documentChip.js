/*
 * documentChip — inline Verweis-Chip auf einen Beleg. Atom-Node, Inhalt liegt
 * in Attributen. Klick dispatcht ein DOM-Event (pm-note:navigate); die echte
 * Reader-Navigation (Seiten-Anker + previewReloadNonce) kommt in M4.
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import DocumentChipView from './DocumentChipView.vue';

export const DocumentChip = Node.create({
  name: 'documentChip',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      docId: { default: null },
      title: { default: '' },
      insertedAt: { default: null, rendered: false },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-document-chip]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-document-chip': '' }, HTMLAttributes), HTMLAttributes.title || ''];
  },

  addNodeView() {
    return VueNodeViewRenderer(DocumentChipView);
  },

  addCommands() {
    return {
      insertDocumentChip: (attrs) => ({ chain }) =>
        chain()
          .insertContent([{
            type: this.name,
            attrs: { ...attrs, insertedAt: new Date().toISOString() },
          }, { type: 'text', text: ' ' }])
          .run(),
    };
  },
});

export default DocumentChip;

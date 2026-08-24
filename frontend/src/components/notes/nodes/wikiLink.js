/*
 * wikiLink — inline [[…]]-Verweis auf ein anderes Objekt (Notiz, Beleg,
 * Korrespondent, Dossier). Atom-Node. In M5 speist er die Rückverweise der
 * Wissensbasis (note_link); hier dispatcht ein Klick nur pm-note:navigate.
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import WikiLinkView from './WikiLinkView.vue';

export const WikiLink = Node.create({
  name: 'wikiLink',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      targetType: { default: 'note' }, // document | correspondent | dossier | note
      targetId: { default: null },
      label: { default: '' },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-wiki-link]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-wiki-link': '' }, HTMLAttributes), `[[${HTMLAttributes.label || ''}]]`];
  },

  addNodeView() {
    return VueNodeViewRenderer(WikiLinkView);
  },

  addCommands() {
    return {
      insertWikiLink: (attrs) => ({ chain }) =>
        chain()
          .insertContent([{ type: this.name, attrs }, { type: 'text', text: ' ' }])
          .run(),
    };
  },
});

export default WikiLink;

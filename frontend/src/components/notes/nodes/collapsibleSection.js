import { Node, VueNodeViewRenderer } from '@tiptap/vue-3';
import CollapsibleSectionView from './CollapsibleSectionView.vue';

export const CollapsibleSection = Node.create({
  name: 'collapsibleSection',
  group: 'block',
  content: 'block+',
  defining: true,
  isolating: true,
  addAttributes() {
    return {
      title: { default: 'Abschnitt', parseHTML: el => el.querySelector('summary')?.textContent || 'Abschnitt', rendered: false },
      open: { default: true, parseHTML: el => el.hasAttribute('open'), rendered: false },
    };
  },
  parseHTML() { return [{ tag: 'details[data-note-section]', contentElement: '[data-section-content]' }]; },
  renderHTML({ node }) {
    return ['details', { 'data-note-section': '', ...(node.attrs.open ? { open: '' } : {}) },
      ['summary', {}, node.attrs.title], ['div', { 'data-section-content': '' }, 0]];
  },
  addNodeView() { return VueNodeViewRenderer(CollapsibleSectionView); },
  addCommands() {
    return { insertCollapsibleSection: () => ({ commands }) => commands.insertContent({
      type: this.name, content: [{ type: 'paragraph' }],
    }) };
  },
});

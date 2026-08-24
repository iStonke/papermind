/*
 * aiBlock — abgesetzte KI-Antwort mit Quellen-Fußnoten. Atom-Block; Text +
 * Quellen liegen in Attributen. `stale` markiert, dass sich eine Quelle seit
 * der Antwort geändert haben könnte (Versions-Bindung kommt in M5).
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import AiBlockView from './AiBlockView.vue';

export const AiBlock = Node.create({
  name: 'aiBlock',
  group: 'block',
  atom: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      text: { default: '' },
      prompt: { default: '' },
      provider: { default: '' },
      model: { default: '' },
      generatedAt: { default: null },
      sources: { default: [] },
      stale: { default: false },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-ai-block]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes({ 'data-ai-block': '' }, HTMLAttributes), HTMLAttributes.text || ''];
  },

  addNodeView() {
    return VueNodeViewRenderer(AiBlockView);
  },

  addCommands() {
    return {
      insertAiBlock: (attrs) => ({ chain }) =>
        chain().insertContent({ type: this.name, attrs }).run(),
    };
  },
});

export default AiBlock;

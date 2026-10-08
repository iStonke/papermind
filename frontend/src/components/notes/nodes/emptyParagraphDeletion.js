import { Extension } from '@tiptap/core';
import { Selection } from '@tiptap/pm/state';

// Empty spacer paragraphs can be removed even beside non-selectable boxes.
// Respect each container's schema (e.g. the required first list paragraph).
export const EmptyParagraphDeletion = Extension.create({
  name: 'emptyParagraphDeletion',
  priority: 110,
  addKeyboardShortcuts() {
    const removeEmptyParagraph = (direction) => {
      const { state, view } = this.editor;
      const { empty, $from } = state.selection;
      if (!empty || !$from.depth || $from.parent.type.name !== 'paragraph'
        || $from.parent.content.size !== 0) return false;
      const container = $from.node(-1);
      const index = $from.index(-1);
      if (!container.canReplace(index, index + 1)) {
        // Do not let the fallback delete an adjacent quote instead.
        return container.maybeChild(index + 1)?.type.name === 'ocrQuote';
      }
      const from = $from.before();
      const tr = state.tr.delete(from, $from.after());
      tr.setSelection(Selection.near(tr.doc.resolve(Math.min(from, tr.doc.content.size)), direction));
      view.dispatch(tr.scrollIntoView());
      return true;
    };
    return {
      Backspace: () => removeEmptyParagraph(-1),
      Delete: () => removeEmptyParagraph(1),
    };
  },
});

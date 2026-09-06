import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

const cleanupReviewAnchorKey = new PluginKey('paperMindCleanupReviewAnchor');

function clampPosition(value, doc) {
  return Math.max(0, Math.min(Number(value) || 0, doc.content.size));
}

export const CleanupReviewAnchor = Extension.create({
  name: 'paperMindCleanupReviewAnchor',

  addOptions() {
    return {
      onMount: null,
      onDestroy: null,
    };
  },

  addProseMirrorPlugins() {
    const options = this.options;
    return [new Plugin({
      key: cleanupReviewAnchorKey,
      state: {
        init: () => DecorationSet.empty,
        apply(transaction, decorations) {
          const update = transaction.getMeta(cleanupReviewAnchorKey);
          if (update?.hide) return DecorationSet.empty;
          if (Number.isInteger(update?.position)) {
            const position = clampPosition(update.position, transaction.doc);
            return DecorationSet.create(transaction.doc, [
              Decoration.widget(position, () => {
                const anchor = document.createElement('div');
                anchor.className = 'pm-cleanup-review-anchor';
                anchor.contentEditable = 'false';
                anchor.setAttribute('data-cleanup-review-anchor', '');
                queueMicrotask(() => options.onMount?.(anchor));
                return anchor;
              }, {
                side: 1,
                key: 'paperMindCleanupReviewAnchor',
                destroy: (anchor) => options.onDestroy?.(anchor),
              }),
            ]);
          }
          return decorations.map(transaction.mapping, transaction.doc);
        },
      },
      props: {
        decorations(state) {
          return cleanupReviewAnchorKey.getState(state) || DecorationSet.empty;
        },
      },
    })];
  },
});

export function showCleanupReviewAnchor(editor, position) {
  if (!editor || editor.isDestroyed) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(cleanupReviewAnchorKey, { position })
      .setMeta('addToHistory', false),
  );
}

export function hideCleanupReviewAnchor(editor) {
  if (!editor || editor.isDestroyed) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(cleanupReviewAnchorKey, { hide: true })
      .setMeta('addToHistory', false),
  );
}

export default CleanupReviewAnchor;

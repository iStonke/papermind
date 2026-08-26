import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

const historyFlashKey = new PluginKey('noteHistoryFlash');

function clampPosition(value, doc) {
  return Math.max(0, Math.min(Number(value) || 0, doc.content.size));
}

function decorationsForRange(doc, range) {
  const from = clampPosition(range?.from, doc);
  const to = Math.max(from, clampPosition(range?.to, doc));

  if (to > from) {
    return [Decoration.inline(from, to, {
      class: 'pm-history-flash',
      'data-history-flash': '',
    })];
  }

  // Gelöschter Text besitzt danach keinen sichtbaren Bereich mehr. Hier keine
  // Ersatzmarke einsetzen: Neben dem echten Browser-Caret wirkte sie wie eine
  // zweite Schreibmarke und war dadurch missverständlich.
  return [];
}

export const HistoryFlash = Extension.create({
  name: 'historyFlash',

  addProseMirrorPlugins() {
    return [new Plugin({
      key: historyFlashKey,
      state: {
        init: () => DecorationSet.empty,
        apply(transaction, decorations) {
          const meta = transaction.getMeta(historyFlashKey);
          if (meta?.clear) return DecorationSet.empty;
          if (meta?.range) {
            return DecorationSet.create(transaction.doc, decorationsForRange(transaction.doc, meta.range));
          }
          return decorations.map(transaction.mapping, transaction.doc);
        },
      },
      props: {
        decorations(state) {
          return historyFlashKey.getState(state);
        },
      },
    })];
  },
});

export function historyChangedRange(beforeDoc, afterDoc) {
  const start = beforeDoc?.content?.findDiffStart?.(afterDoc?.content);
  if (start == null || !afterDoc?.content) return null;
  const end = beforeDoc.content.findDiffEnd(afterDoc.content);
  const from = clampPosition(start, afterDoc);
  const to = Math.max(from, clampPosition(end?.b ?? start, afterDoc));
  return { from, to };
}

export function showHistoryFlash(editor, range) {
  if (!editor || editor.isDestroyed || !range) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(historyFlashKey, { range })
      .setMeta('addToHistory', false),
  );
}

export function clearHistoryFlash(editor) {
  if (!editor || editor.isDestroyed) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(historyFlashKey, { clear: true })
      .setMeta('addToHistory', false),
  );
}

export default HistoryFlash;

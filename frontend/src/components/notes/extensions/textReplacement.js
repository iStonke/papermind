import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

export const textReplacementPluginKey = new PluginKey('noteTextReplacement');

export function findTextReplacement(state, replacements) {
  const { selection } = state;
  if (!selection.empty || !selection.$from.parent.isTextblock) return null;

  const { $from } = selection;
  if ($from.parent.type.spec.code) return null;
  if ($from.marks().some((mark) => mark.type.name === 'code')) return null;
  for (let depth = $from.depth; depth > 0; depth -= 1) {
    if ($from.node(depth).type.name === 'templateField') return null;
  }

  const textBefore = $from.parent.textBetween(0, $from.parentOffset, undefined, '\ufffc');
  const token = textBefore.match(/(?:^|\s)(\S+)$/)?.[1];
  if (!token) return null;

  const match = (Array.isArray(replacements) ? replacements : []).find((item) => (
    item?.enabled !== false
    && item?.shortcut === token
    && typeof item?.replacement === 'string'
    && item.replacement.length > 0
  ));
  if (!match) return null;

  return {
    from: selection.from - token.length,
    to: selection.from,
    replacement: match.replacement,
  };
}

export function applyTextReplacement(view, replacements) {
  const match = findTextReplacement(view.state, replacements);
  if (!match) return false;
  view.dispatch(view.state.tr.insertText(match.replacement, match.from, match.to));
  return true;
}

export function textReplacementDecorations(state, replacements) {
  const match = findTextReplacement(state, replacements);
  if (!match) return DecorationSet.empty;

  const shortcutDecoration = Decoration.inline(match.from, match.to, {
    class: 'pm-text-replacement-trigger',
  });
  const hintDecoration = Decoration.widget(match.to, () => {
    const hint = document.createElement('span');
    hint.className = 'pm-text-replacement-hint';
    hint.setAttribute('aria-hidden', 'true');
    hint.setAttribute('contenteditable', 'false');
    hint.dataset.textReplacementHint = '';
    hint.textContent = `Enter → ${match.replacement}`;
    hint.title = `Enter drücken: ${match.replacement}`;
    return hint;
  }, {
    key: `text-replacement:${match.from}:${match.replacement}`,
    side: 1,
  });

  return DecorationSet.create(state.doc, [shortcutDecoration, hintDecoration]);
}

export const NoteTextReplacement = Extension.create({
  name: 'noteTextReplacement',
  priority: 1100,

  addOptions() {
    return {
      getReplacements: () => [],
    };
  },

  addProseMirrorPlugins() {
    return [new Plugin({
      key: textReplacementPluginKey,
      props: {
        decorations: (state) => textReplacementDecorations(
          state,
          this.options.getReplacements(),
        ),
        handleKeyDown: (view, event) => {
          if (
            event.key !== 'Enter'
            || event.shiftKey
            || event.metaKey
            || event.ctrlKey
            || event.altKey
            || event.isComposing
          ) {
            return false;
          }
          // Nur die Ersetzung behandeln. `false` laesst anschliessend den normalen
          // ProseMirror-Enter-Befehl laufen, sodass der erwartete Absatz entsteht.
          applyTextReplacement(view, this.options.getReplacements());
          return false;
        },
      },
    })];
  },
});

export default NoteTextReplacement;

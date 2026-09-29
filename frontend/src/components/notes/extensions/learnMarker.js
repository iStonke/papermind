import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

/**
 * Lern-Marker + stabile Node-IDs für den Lernbereich.
 *
 * Fügt zwei globale Attribute an markierbare Block-Knoten:
 *  - `pmId`  – stabile Kurz-ID, damit ein Lernartefakt eine Notizzeile über
 *              spätere Edits hinweg wiederfindet. LAZY: wird erst vergeben, wenn
 *              die Zeile markiert wird (Altnotizen bleiben unberührt).
 *  - `learn` – der Marker-Typ (String: 'lernen' generisch, oder 'fakt'/'warum'/…);
 *              null = nicht markiert.
 *
 * Das Backend (NoteService._sync_learn_markers) projiziert diese Attribute bei
 * jedem Save in die learn_marker-Tabelle. Siehe docs/design/lernbereich-datenmodell.md §1/§3.4.
 */

const MARKABLE_TYPES = [
  'paragraph',
  'heading',
  'blockquote',
  'listItem',
  'taskItem',
  'checkListItem',
];

const MARKER_KINDS = ['lernen', 'fakt', 'warum', 'aufgabe', 'analyse', 'prozess', 'vergleich'];

function randomPmId() {
  try {
    return crypto.randomUUID().replace(/-/g, '').slice(0, 8);
  } catch {
    return Math.random().toString(36).slice(2, 10);
  }
}

function markerKindOf(learn) {
  if (!learn) return null;
  if (typeof learn === 'string') return learn || null;
  return learn.kind || null;
}

export const LearnMarker = Extension.create({
  name: 'learnMarker',

  addOptions() {
    return { kinds: MARKER_KINDS };
  },

  addGlobalAttributes() {
    return [
      {
        types: MARKABLE_TYPES,
        attributes: {
          pmId: {
            default: null,
            keepOnSplit: false,
            parseHTML: (el) => el.getAttribute('data-pm-id') || null,
            renderHTML: (attrs) => (attrs.pmId ? { 'data-pm-id': attrs.pmId } : {}),
          },
          learn: {
            default: null,
            keepOnSplit: false,
            parseHTML: (el) => el.getAttribute('data-learn') || null,
            renderHTML: (attrs) => {
              const kind = markerKindOf(attrs.learn);
              if (!kind) return {};
              const partial = typeof attrs.learnText === 'string' && attrs.learnText.trim();
              return {
                'data-learn': kind,
                class: partial ? 'pm-learn-marked pm-learn-partial' : 'pm-learn-marked',
              };
            },
          },
          learnText: { default: null, keepOnSplit: false, renderHTML: () => ({}) },
          learnFrom: { default: null, keepOnSplit: false, renderHTML: () => ({}) },
          learnTo: { default: null, keepOnSplit: false, renderHTML: () => ({}) },
        },
      },
    ];
  },

  addCommands() {
    // Nächsten markierbaren Block-Knoten an der Auswahl finden (Tiefe von innen).
    const findMarkable = (state) => {
      const { $from } = state.selection;
      for (let d = $from.depth; d >= 1; d -= 1) {
        const node = $from.node(d);
        if (MARKABLE_TYPES.includes(node.type.name)) {
          return { pos: $from.before(d), node };
        }
      }
      return null;
    };

    return {
      // Setzt/wechselt den Marker; gleicher Typ = entfernen (Toggle).
      toggleLearnMarker:
        (kind = 'lernen', wholeBlock = false) =>
        ({ state, tr, dispatch }) => {
          const target = findMarkable(state);
          if (!target) return false;
          const { pos, node } = target;
          const current = markerKindOf(node.attrs.learn);
          const attrs = { ...node.attrs };
          const contentStart = pos + 1;
          const selectionFrom = Math.max(0, state.selection.from - contentStart);
          const selectionTo = Math.min(node.content.size, state.selection.to - contentStart);
          const hasSelection = !wholeBlock && selectionTo > selectionFrom;
          const learnText = hasSelection
            ? state.doc.textBetween(contentStart + selectionFrom, contentStart + selectionTo, ' ').trim()
            : null;
          const learnFrom = learnText ? selectionFrom : null;
          const learnTo = learnText ? selectionTo : null;
          const isSameSelection = current === kind
            && attrs.learnText === learnText
            && attrs.learnFrom === learnFrom
            && attrs.learnTo === learnTo;
          if (isSameSelection) {
            attrs.learn = null;
            attrs.learnText = null;
            attrs.learnFrom = null;
            attrs.learnTo = null;
          } else {
            attrs.learn = kind;
            attrs.learnText = learnText;
            attrs.learnFrom = learnFrom;
            attrs.learnTo = learnTo;
            if (!attrs.pmId) attrs.pmId = randomPmId();
          }
          if (dispatch) dispatch(tr.setNodeMarkup(pos, undefined, attrs));
          return true;
        },

      clearLearnMarker:
        () =>
        ({ state, tr, dispatch }) => {
          const target = findMarkable(state);
          if (!target) return false;
          const { pos, node } = target;
          if (!markerKindOf(node.attrs.learn)) return false;
          if (dispatch) dispatch(tr.setNodeMarkup(pos, undefined, {
            ...node.attrs,
            learn: null,
            learnText: null,
            learnFrom: null,
            learnTo: null,
          }));
          return true;
        },
    };
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('learnMarkerSelection'),
        props: {
          decorations(state) {
            const decorations = [];
            state.doc.descendants((node, pos) => {
              if (!MARKABLE_TYPES.includes(node.type.name) || !markerKindOf(node.attrs.learn)) return;
              const from = Number(node.attrs.learnFrom);
              const to = Number(node.attrs.learnTo);
              if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to <= from || to > node.content.size) return;
              decorations.push(Decoration.inline(pos + 1 + from, pos + 1 + to, {
                class: 'pm-learn-selection',
              }));
            });
            return DecorationSet.create(state.doc, decorations);
          },
        },
      }),
    ];
  },

  addKeyboardShortcuts() {
    // Eine Taste, kein Nachdenken: generischer Marker auf die aktuelle Zeile.
    return {
      'Mod-Shift-m': () => this.editor.commands.toggleLearnMarker('lernen'),
    };
  },
});

export default LearnMarker;

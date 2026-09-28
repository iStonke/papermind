import { Extension } from '@tiptap/core';

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
              return { 'data-learn': kind, class: 'pm-learn-marked' };
            },
          },
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
        (kind = 'lernen') =>
        ({ state, tr, dispatch }) => {
          const target = findMarkable(state);
          if (!target) return false;
          const { pos, node } = target;
          const current = markerKindOf(node.attrs.learn);
          const attrs = { ...node.attrs };
          if (current === kind) {
            attrs.learn = null;
          } else {
            attrs.learn = kind;
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
          if (dispatch) dispatch(tr.setNodeMarkup(pos, undefined, { ...node.attrs, learn: null }));
          return true;
        },
    };
  },

  addKeyboardShortcuts() {
    // Eine Taste, kein Nachdenken: generischer Marker auf die aktuelle Zeile.
    return {
      'Mod-Shift-m': () => this.editor.commands.toggleLearnMarker('lernen'),
    };
  },
});

export default LearnMarker;

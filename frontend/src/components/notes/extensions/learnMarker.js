import { Extension } from '@tiptap/core';
import { NodeSelection, Plugin, PluginKey } from '@tiptap/pm/state';
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
  // Dokument-Zitat (atomarer Block): Zitate aus dem Skript direkt als Lernstoff.
  'ocrQuote',
];

const MARKER_KINDS = ['lernen', 'fakt', 'warum', 'aufgabe', 'analyse', 'prozess', 'vergleich'];

export function randomPmId() {
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

// Rückkopplung aus dem Lernbereich: abgeleiteter Status je Markierung (pmId).
//   open   – noch keine vollständige Karte (Nachbereitung offen)
//   card   – Karte angelegt, aber noch nicht sicher gelernt
//   strong – zugehörige Karte(n) als „sicher“ bewertet
const learnMarkerStatusKey = new PluginKey('learnMarkerStatus');
const LEARN_STATES = ['open', 'card', 'strong'];
const LEARN_STATE_LABELS = { open: 'offen', card: 'Karte', strong: 'sicher' };
const LEARN_STATE_TITLES = {
  open: 'Offen – nachbereiten (öffnet den Lernbereich)',
  card: 'Karte angelegt – zum Öffnen klicken',
  strong: 'Sicher gelernt – zum Öffnen klicken',
};

// Status-Eintrag normalisieren: akzeptiert sowohl einen reinen State-String als
// auch ein Objekt mit Sprungzielen (cardId/sheetId/courseId).
function normalizeStatusEntry(value) {
  if (!value) return null;
  if (typeof value === 'string') {
    return LEARN_STATES.includes(value) ? { state: value } : null;
  }
  const state = LEARN_STATES.includes(value.state) ? value.state : 'open';
  return {
    state,
    cardId: value.cardId || null,
    sheetId: value.sheetId || null,
    courseId: value.courseId || null,
    hasCard: Boolean(value.hasCard),
  };
}

// Baut die klickbare Status-Pille (Widget-Dekoration) für eine markierte Zeile.
function buildStatusChip(pmId, entry, onOpenMarker) {
  const state = entry.state || 'open';
  const el = document.createElement('span');
  el.className = `pm-learn-chip pm-learn-chip--${state}`;
  el.textContent = LEARN_STATE_LABELS[state] || LEARN_STATE_LABELS.open;
  el.setAttribute('data-learn-state', state);
  el.setAttribute('contenteditable', 'false');
  el.setAttribute('role', 'button');
  el.setAttribute('tabindex', '0');
  el.setAttribute('title', LEARN_STATE_TITLES[state] || LEARN_STATE_TITLES.open);
  el.setAttribute('aria-label', `Lernstatus: ${LEARN_STATE_LABELS[state] || 'offen'}. Im Lernbereich öffnen.`);
  const trigger = (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    if (typeof onOpenMarker === 'function') {
      onOpenMarker({
        pmId,
        state,
        cardId: entry.cardId || null,
        sheetId: entry.sheetId || null,
        courseId: entry.courseId || null,
        hasCard: Boolean(entry.hasCard),
      });
    }
  };
  // mousedown abfangen, damit der Editor keine Auswahl/Schreibmarke setzt.
  el.addEventListener('mousedown', (ev) => { ev.preventDefault(); ev.stopPropagation(); });
  el.addEventListener('click', trigger);
  el.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' || ev.key === ' ') trigger(ev);
  });
  return el;
}

export const LearnMarker = Extension.create({
  name: 'learnMarker',

  addOptions() {
    // showStatusChips: nur im bearbeitbaren Editor die klickbare Status-Pille
    //   rendern – NICHT in der schreibgeschützten Vorschau (NotePreview).
    // onOpenMarker: Callback für den Klick auf die Status-Pille (Sprung in den
    //   Lernbereich). Erhält { pmId, state, cardId, sheetId, courseId, hasCard }.
    return { kinds: MARKER_KINDS, showStatusChips: false, onOpenMarker: null };
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
      // Atomare Blöcke (z. B. Dokument-Zitate) sind nur per Block-Auswahl greifbar.
      const { selection } = state;
      if (selection instanceof NodeSelection && MARKABLE_TYPES.includes(selection.node.type.name)) {
        return { pos: selection.from, node: selection.node };
      }
      const { $from } = selection;
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

      // Marker an einer festen Position umschalten (für Node-Views wie das
      // Dokument-Zitat, die ihren Block selbst kennen). Gleicher Typ = entfernen.
      toggleLearnMarkerAt:
        (pos, kind = 'lernen') =>
        ({ state, tr, dispatch }) => {
          const node = state.doc.nodeAt(pos);
          if (!node || !MARKABLE_TYPES.includes(node.type.name)) return false;
          const marked = markerKindOf(node.attrs.learn) === kind;
          const attrs = {
            ...node.attrs,
            learn: marked ? null : kind,
            learnText: null,
            learnFrom: null,
            learnTo: null,
          };
          if (!marked && !attrs.pmId) attrs.pmId = randomPmId();
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

      // Setzt die aus dem Lernbereich geladene Status-Karte (pmId → open|card|strong).
      // Rein dekorativ (keine Dokumentänderung), damit Undo/History unberührt bleiben.
      setLearnMarkerStatuses:
        (map = {}) =>
        ({ tr, dispatch }) => {
          if (dispatch) dispatch(tr.setMeta(learnMarkerStatusKey, map && typeof map === 'object' ? map : {}));
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
      // Status-Rückkopplung: färbt markierte Zeilen nach ihrem Lern-Fortschritt
      // und hängt eine klickbare Status-Pille an (Sprung in den Lernbereich).
      new Plugin({
        key: learnMarkerStatusKey,
        state: {
          init: () => ({}),
          apply(tr, value) {
            const meta = tr.getMeta(learnMarkerStatusKey);
            return meta && typeof meta === 'object' ? meta : value;
          },
        },
        props: {
          decorations: (state) => {
            const map = learnMarkerStatusKey.getState(state) || {};
            const decorations = [];
            state.doc.descendants((node, pos) => {
              if (!MARKABLE_TYPES.includes(node.type.name)) return;
              if (!markerKindOf(node.attrs.learn) || !node.attrs.pmId) return;
              const pmId = node.attrs.pmId;
              const entry = normalizeStatusEntry(map[pmId]) || { state: 'open' };
              const review = entry.state;
              decorations.push(Decoration.node(pos, pos + node.nodeSize, {
                class: `pm-learn-state pm-learn-state--${review}`,
                'data-learn-state': review,
              }));
              // Klickbare Pille am Zeilenende (echtes DOM-Element statt ::after).
              // Nur im bearbeitbaren Editor, nicht in der Vorschau. Atomare
              // Blöcke (Dokument-Zitat) haben keinen Inhalt für ein Widget – sie
              // zeigen ihren Status selbst im Node-View.
              if (this.options.showStatusChips && !node.isAtom) {
                decorations.push(
                  Decoration.widget(
                    pos + node.nodeSize - 1,
                    () => buildStatusChip(pmId, entry, this.options.onOpenMarker),
                    // Ziel in den Key aufnehmen, damit das Widget neu gebaut wird,
                    // sobald sich Zustand ODER Sprungziel ändert (Entwurf → Karte).
                    { side: 1, ignoreSelection: true, key: `lmchip-${pmId}-${review}-${entry.cardId || 'none'}` },
                  ),
                );
              }
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

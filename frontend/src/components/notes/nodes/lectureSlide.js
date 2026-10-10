/*
 * lectureSlide — Mitschrift-Abschnitt „Folie + Mitschrift" (Online-Vorlesung
 * ohne Foliensatz). Ein Abschnitt besteht aus zwei festen Spalten:
 *
 *   lectureSlideMedia  – links der Screenshot als gewöhnlicher `image`-Knoten
 *                        (Upload, Bildunterschrift, Kopieren, Archiv-Export
 *                        funktionieren dadurch unverändert); leer = Platzhalter
 *   lectureSlideNotes  – rechts die Mitschrift als normale Blöcke (Listen,
 *                        Zitate, „zu lernen"-Marker wie überall)
 *
 * Jeder Screenshot beginnt einen neuen Abschnitt; die Mitschrift steht immer
 * auf Höhe ihrer Folie. Ob Folie und Mitschrift nebeneinander, untereinander
 * oder (nur Mitschrift) ohne sichtbare Folie stehen, entscheidet allein das
 * Notiz-Attribut `lectureLayout` (lectureLayout.js) – das Umschalten verändert
 * den Inhalt nicht.
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import { Plugin, TextSelection } from '@tiptap/pm/state';
import LectureSlideView from './LectureSlideView.vue';
import LectureSlideMediaView from './LectureSlideMediaView.vue';

import { lectureSlideJSON } from './lectureSlideContent.js';
export { lectureSlideJSON } from './lectureSlideContent.js';

/** Mitschrift-Abschnitt, in dem die Auswahl liegt (mit absoluter Position). */
export function lectureSlideAtSelection(state) {
  const { $from } = state.selection;
  for (let depth = $from.depth; depth > 0; depth -= 1) {
    const node = $from.node(depth);
    if (node.type.name === 'lectureSlide') return { node, pos: $from.before(depth), depth };
  }
  return null;
}

/** Cursor in den ersten Mitschrift-Absatz des Abschnitts an `slidePos` setzen. */
function selectSlideNotes(tr, slidePos) {
  const slide = tr.doc.nodeAt(slidePos);
  if (!slide) return;
  const notesPos = slidePos + 1 + slide.firstChild.nodeSize;
  tr.setSelection(TextSelection.near(tr.doc.resolve(notesPos + 1)));
}

export const LectureSlideMedia = Node.create({
  name: 'lectureSlideMedia',
  content: 'image?',
  isolating: true,
  selectable: false,
  draggable: false,

  addOptions() {
    // onRequestImage(mediaPos): Klick auf den leeren Platzhalter – der Editor
    // öffnet die Dateiauswahl und legt das Bild genau in diese Folie.
    return { onRequestImage: null, onPasteImage: null };
  },

  parseHTML() {
    return [{ tag: 'div[data-lecture-slide-media]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes({ 'data-lecture-slide-media': '', class: 'pm-lecture-slide__media' }, HTMLAttributes), 0];
  },

  addNodeView() {
    return VueNodeViewRenderer(LectureSlideMediaView);
  },
});

export const LectureSlideNotes = Node.create({
  name: 'lectureSlideNotes',
  content: 'block+',
  isolating: true,
  selectable: false,
  draggable: false,

  parseHTML() {
    return [{ tag: 'div[data-lecture-slide-notes]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes({ 'data-lecture-slide-notes': '', class: 'pm-lecture-slide__notes' }, HTMLAttributes), 0];
  },
});

export const LectureSlide = Node.create({
  name: 'lectureSlide',
  group: 'block',
  content: 'lectureSlideMedia lectureSlideNotes',
  defining: true,
  isolating: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return { capturedAt: {
      default: null,
      parseHTML: element => element.getAttribute('data-captured-at'),
      renderHTML: attrs => attrs.capturedAt ? { 'data-captured-at': attrs.capturedAt } : {},
    } };
  },

  addNodeView() { return VueNodeViewRenderer(LectureSlideView); },

  addProseMirrorPlugins() {
    return [new Plugin({
      appendTransaction(transactions, oldState, state) {
        if (!transactions.some(tr => tr.docChanged) || transactions.some(tr => tr.getMeta('preventUpdate'))) return null;
        const unchanged = new Set();
        oldState.doc.descendants(node => { if (node.type.name === 'lectureSlide') unchanged.add(node); });
        const tr = state.tr;
        state.doc.descendants((node, pos) => {
          if (node.type.name !== 'lectureSlide' || node.attrs.capturedAt || unchanged.has(node)) return;
          if (!node.textContent.trim() && !node.firstChild.childCount) return;
          tr.setNodeMarkup(pos, undefined, { ...node.attrs, capturedAt: new Date().toISOString() });
        });
        return tr.docChanged ? tr : null;
      },
    })];
  },

  parseHTML() {
    return [{ tag: 'section[data-lecture-slide]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes({ 'data-lecture-slide': '', class: 'pm-lecture-slide' }, HTMLAttributes), 0];
  },

  addCommands() {
    return {
      // Neuer Abschnitt hinter dem aktuellen Abschnitt bzw. dem aktuellen Block
      // der obersten Ebene; ein leerer Absatz an dieser Stelle wird ersetzt.
      // Danach steht der Cursor in der Mitschrift des neuen Abschnitts.
      insertLectureSlide: (imageAttrs = null) => ({ state, tr, dispatch, editor }) => {
        const slide = editor.schema.nodeFromJSON(lectureSlideJSON(imageAttrs));
        const context = lectureSlideAtSelection(state);
        const { $from } = state.selection;
        let at;
        if (context) {
          at = context.pos + context.node.nodeSize;
        } else if ($from.depth >= 1) {
          const top = $from.node(1);
          const topPos = $from.before(1);
          if (top.type.name === 'paragraph' && top.content.size === 0) {
            if (dispatch) {
              tr.replaceWith(topPos, topPos + top.nodeSize, slide);
              selectSlideNotes(tr, topPos);
              dispatch(tr.scrollIntoView());
            }
            return true;
          }
          at = $from.after(1);
        } else {
          at = state.selection.to;
        }
        if (dispatch) {
          tr.insert(at, slide);
          selectSlideNotes(tr, at);
          dispatch(tr.scrollIntoView());
        }
        return true;
      },

      // Bild in die (leere) Folie des Abschnitts an `mediaPos` legen.
      setLectureSlideImage: (mediaPos, imageAttrs) => ({ state, tr, dispatch, editor }) => {
        const media = state.doc.nodeAt(mediaPos);
        if (!media || media.type.name !== 'lectureSlideMedia' || !imageAttrs) return false;
        const image = editor.schema.nodes.image.create(imageAttrs);
        if (dispatch) {
          tr.replaceWith(mediaPos + 1, mediaPos + 1 + media.content.size, image);
          const slidePos = state.doc.resolve(mediaPos).before();
          selectSlideNotes(tr, slidePos);
          dispatch(tr.scrollIntoView());
        }
        return true;
      },
    };
  },
});

export default LectureSlide;

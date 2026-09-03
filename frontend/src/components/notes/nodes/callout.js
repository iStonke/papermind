import { Node, mergeAttributes, VueNodeViewRenderer, wrappingInputRule } from '@tiptap/vue-3';
import { normalizeNoteCalloutKind } from '../../../utils/noteCallouts.js';
import CalloutView from './CalloutView.vue';

/**
 * Zeilenanfang-Kürzel für das Mitschreiben im Meetingtempo: ein Zeichen plus
 * Leerzeichen wandelt den aktuellen Absatz sofort in den passenden Hinweisblock
 * um – ganz ohne Slash-Menü. Die Zeichen sind bewusst kollisionsfrei zu den
 * Markdown-Regeln von StarterKit (`#`, `-`, `>`, `1.` …) gewählt.
 */
export const CALLOUT_INPUT_SHORTCUTS = Object.freeze([
  { find: /^\?\s$/, kind: 'question' },
  { find: /^!\s$/, kind: 'important' },
  { find: /^=\s$/, kind: 'decision' },
]);

/**
 * Strukturierter PaperMind-Hinweisblock. Der Typ bleibt als Attribut im
 * Notiz-JSON erhalten und kann dadurch später gefiltert oder ausgewertet
 * werden; der eigentliche Inhalt bleibt normal editierbarer ProseMirror-Text.
 */
export const Callout = Node.create({
  name: 'callout',
  group: 'block',
  content: 'block+',
  defining: true,
  selectable: true,
  draggable: false,

  addAttributes() {
    return {
      kind: {
        default: 'important',
        parseHTML: (element) => normalizeNoteCalloutKind(element.getAttribute('data-callout')),
        renderHTML: (attributes) => ({ 'data-callout': normalizeNoteCalloutKind(attributes.kind) }),
      },
      insertedAt: {
        default: null,
        rendered: false,
      },
    };
  },

  parseHTML() {
    return [{ tag: 'aside[data-callout]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['aside', mergeAttributes(HTMLAttributes), 0];
  },

  addNodeView() {
    return VueNodeViewRenderer(CalloutView);
  },

  addCommands() {
    return {
      insertCallout: (kind = 'important') => ({ commands }) => commands.insertContent({
        type: this.name,
        attrs: {
          kind: normalizeNoteCalloutKind(kind),
          insertedAt: new Date().toISOString(),
        },
        content: [{ type: 'paragraph' }],
      }),
      setCalloutKind: (kind) => ({ commands }) => commands.updateAttributes(
        this.name,
        { kind: normalizeNoteCalloutKind(kind) },
      ),
    };
  },

  addInputRules() {
    return CALLOUT_INPUT_SHORTCUTS.map(({ find, kind }) =>
      wrappingInputRule({
        find,
        type: this.type,
        // Frischer Zeitstempel ⇒ identische „Ankunfts"-Animation wie beim
        // Einfügen über das Slash-Menü (CalloutView liest attrs.insertedAt).
        getAttributes: () => ({
          kind: normalizeNoteCalloutKind(kind),
          insertedAt: new Date().toISOString(),
        }),
      }),
    );
  },
});

export default Callout;

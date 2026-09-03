import { Mark, mergeAttributes } from '@tiptap/vue-3';

import {
  normalizeNoteHighlightColor,
  noteHighlightInlineStyle,
} from '../../../utils/noteHighlights.js';

/** Mehrfarbiger, sicher auf eine feste PaperMind-Palette begrenzter Textmarker. */
export const NoteHighlight = Mark.create({
  name: 'highlight',

  addAttributes() {
    return {
      color: {
        default: 'yellow',
        parseHTML: (element) => normalizeNoteHighlightColor(
          element.getAttribute('data-highlight'),
        ),
        renderHTML: (attributes) => {
          const color = normalizeNoteHighlightColor(attributes.color);
          return {
            'data-highlight': color,
            style: noteHighlightInlineStyle(color),
          };
        },
      },
    };
  },

  parseHTML() {
    return [{ tag: 'mark' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['mark', mergeAttributes({ class: 'pm-text-highlight' }, HTMLAttributes), 0];
  },

  addCommands() {
    return {
      setNoteHighlight: (color = 'yellow') => ({ commands }) => commands.setMark(
        this.name,
        { color: normalizeNoteHighlightColor(color) },
      ),
      unsetNoteHighlight: () => ({ commands }) => commands.unsetMark(this.name),
    };
  },

  addKeyboardShortcuts() {
    return {
      'Mod-Shift-h': () => this.editor.commands.setNoteHighlight('yellow'),
    };
  },
});

export default NoteHighlight;

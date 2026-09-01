import Image from '@tiptap/extension-image';
import { mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';

import NoteImageView from './NoteImageView.vue';
import { normalizeNoteImageWidth } from './noteImageAttrs.js';

export { normalizeNoteImageWidth } from './noteImageAttrs.js';

/**
 * Private PaperMind image node. The JSON stores only the stable, token-free API
 * path; the Vue node view attaches the short-lived file token while rendering.
 */
export const NoteImage = Image.extend({
  addAttributes() {
    return {
      src: {
        default: null,
        rendered: false,
        parseHTML: (element) => element.querySelector('img')?.getAttribute('src') || null,
      },
      alt: {
        default: '',
        rendered: false,
        parseHTML: (element) => element.querySelector('img')?.getAttribute('alt') || '',
      },
      title: {
        default: '',
        rendered: false,
        parseHTML: (element) => element.querySelector('img')?.getAttribute('title') || '',
      },
      width: { default: null, rendered: false },
      height: { default: null, rendered: false },
      imageId: {
        default: null,
        rendered: false,
        parseHTML: (element) => element.getAttribute('data-image-id'),
      },
      noteId: {
        default: null,
        rendered: false,
        parseHTML: (element) => element.getAttribute('data-note-id'),
      },
      caption: {
        default: '',
        rendered: false,
        parseHTML: (element) => element.querySelector('figcaption')?.textContent || '',
      },
      displayWidth: {
        default: 100,
        rendered: false,
        parseHTML: (element) => normalizeNoteImageWidth(element.getAttribute('data-display-width')),
      },
    };
  },

  // Pasted third-party <img> elements are deliberately not accepted. Images
  // enter the document only after PaperMind has validated and stored the file.
  parseHTML() {
    return [{ tag: 'figure[data-note-image]' }];
  },

  renderHTML({ node, HTMLAttributes }) {
    const attrs = node.attrs || {};
    const figureAttrs = mergeAttributes(HTMLAttributes, {
      'data-note-image': '',
      'data-image-id': attrs.imageId || '',
      'data-note-id': attrs.noteId || '',
      'data-display-width': normalizeNoteImageWidth(attrs.displayWidth),
    });
    const image = ['img', {
      src: attrs.src || '',
      alt: attrs.alt || '',
      title: attrs.title || '',
      width: attrs.width || undefined,
      height: attrs.height || undefined,
    }];
    return attrs.caption
      ? ['figure', figureAttrs, image, ['figcaption', {}, attrs.caption]]
      : ['figure', figureAttrs, image];
  },

  addNodeView() {
    return VueNodeViewRenderer(NoteImageView);
  },

  addCommands() {
    return {
      ...this.parent?.(),
      insertNoteImage: (attrs) => ({ commands }) => commands.insertContent({
        type: this.name,
        attrs: {
          ...attrs,
          displayWidth: normalizeNoteImageWidth(attrs?.displayWidth),
        },
      }),
    };
  },
}).configure({
  inline: false,
  allowBase64: false,
});

export default NoteImage;

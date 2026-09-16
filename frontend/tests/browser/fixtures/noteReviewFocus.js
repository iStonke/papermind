import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { TableKit } from '@tiptap/extension-table';
import Image from '@tiptap/extension-image';
import NoteEditor from '../../../src/components/notes/NoteEditor.vue';
import { NoteReviewDecorations, setReviewDecorations, clearReviewDecorations } from '../../../src/components/notes/extensions/reviewDecorations.js';

export function mountReviewFocus() {
  const root = document.querySelector('#editor');
  root.setAttribute(NoteEditor.__scopeId, '');
  const editor = new Editor({
    element: root,
    extensions: [StarterKit, TableKit, Image.configure({ allowBase64: true }), NoteReviewDecorations],
    editorProps: { attributes: { class: 'pm-content' } },
    content: '<h2>Überschrift</h2><blockquote><p>Zitat mit eigener Farbe</p></blockquote><ul><li><p>Davor <strong>Fokus</strong> danach <a href="https://example.com">Link</a></p><ul><li><p>Verschachtelt</p></li></ul></li><li><p>Anderer Eintrag</p></li></ul><pre><code>Codeblock</code></pre><table><tbody><tr><th><p>Kopf</p></th><td><p>Zelle</p></td></tr></tbody></table><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="Bild" />',
  });
  // Eigene Farben reproduzieren den Fehler der bisherigen Farbvererbung.
  root.querySelector('h2').style.color = 'rgb(180, 0, 0)';
  root.querySelector('blockquote').style.color = 'rgb(0, 80, 180)';
  let from;
  editor.state.doc.descendants((node, pos) => {
    if (node.isText && node.text === 'Fokus') from = pos;
  });
  window.reviewFixture = { editor, clearReviewDecorations, setReviewDecorations, from };
  setReviewDecorations(editor, [{
    id: 1, from, to: from + 5, focused: true,
    class: 'pm-review-underline pm-review-underline--fix is-focus is-rejected',
    number: 1, numberClass: 'pm-review-num is-focus is-rejected',
  }]);
}

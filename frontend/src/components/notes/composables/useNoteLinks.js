import { nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';
import { normalizeNoteHref, noteHrefLabel } from '../../../utils/noteLinks.js';

export function useNoteLinks({
  editor,
  surfaceEl,
  props,
  overlays,
  clampMenuLeft,
}) {
  const linkInputEl = ref(null);
  let linkCopiedTimer = null;
  const linkEditor = reactive({
    open: false,
    href: '',
    existing: false,
    copied: false,
    error: '',
    range: { from: 0, to: 0 },
    style: {},
  });

  function positionLinkEditor() {
    const ed = editor.value;
    const surface = surfaceEl.value;
    if (!ed || !surface) return;
    const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
    const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
    const rect = posToDOMRect(ed.view, from, to);
    const box = surface.getBoundingClientRect();
    linkEditor.style = {
      left: `${clampMenuLeft(rect.left - box.left, box.width, 360)}px`,
      top: `${rect.bottom - box.top + 4}px`,
    };
  }

  function openLinkEditor(options = null) {
    const ed = editor.value;
    if (!ed) return;
    const explicitRange = Number.isInteger(options?.from) && Number.isInteger(options?.to);
    if (!explicitRange && ed.isActive('link') && ed.state.selection.empty) {
      ed.chain().focus().extendMarkRange('link').run();
    }
    const selection = explicitRange
      ? { from: options.from, to: options.to }
      : { from: ed.state.selection.from, to: ed.state.selection.to };
    const href = String(options?.href || ed.getAttributes('link').href || '');

    linkEditor.range = selection;
    linkEditor.href = href;
    linkEditor.existing = Boolean(href);
    linkEditor.copied = false;
    linkEditor.error = '';
    positionLinkEditor();
    linkEditor.open = true;
    overlays.open('link');
    nextTick(() => {
      linkInputEl.value?.focus();
      linkInputEl.value?.select();
    });
  }

  function closeLinkEditor(restoreFocus = false) {
    linkEditor.open = false;
    linkEditor.error = '';
    linkEditor.copied = false;
    if (restoreFocus) nextTick(() => editor.value?.chain().focus().run());
  }

  function applyLink() {
    const ed = editor.value;
    const normalizedHref = normalizeNoteHref(linkEditor.href);
    if (!ed || !normalizedHref) {
      linkEditor.error = 'Bitte eine gültige Web- oder E-Mail-Adresse eingeben.';
      return;
    }
    const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
    const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
    const attrs = { href: normalizedHref, target: '_blank', rel: 'noopener noreferrer' };
    linkEditor.open = false;

    if (from === to) {
      const label = noteHrefLabel(linkEditor.href, normalizedHref);
      ed.chain()
        .focus()
        .setTextSelection(from)
        // Ein unformatiertes Leerzeichen beendet den Link sauber. Dadurch wird
        // nach dem Einfügen nicht versehentlich im Link weitergeschrieben.
        .insertContent([
          { type: 'text', text: label, marks: [{ type: 'link', attrs }] },
          { type: 'text', text: ' ' },
        ])
        .run();
      return;
    }
    ed.chain().focus().setTextSelection({ from, to }).setLink(attrs).run();
  }

  function removeLink() {
    const ed = editor.value;
    if (!ed) return;
    const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
    const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
    linkEditor.open = false;
    ed.chain().focus().setTextSelection({ from, to }).unsetLink().run();
  }

  function openLinkTarget() {
    const href = normalizeNoteHref(linkEditor.href);
    if (!href) {
      linkEditor.error = 'Dieser Link ist nicht gültig.';
      return;
    }
    if (href.startsWith('mailto:')) window.location.href = href;
    else window.open(href, '_blank', 'noopener,noreferrer');
  }

  async function copyLinkTarget() {
    const href = normalizeNoteHref(linkEditor.href);
    if (!href) {
      linkEditor.error = 'Dieser Link ist nicht gültig.';
      return;
    }
    try {
      await navigator.clipboard.writeText(href);
      linkEditor.copied = true;
      if (linkCopiedTimer) window.clearTimeout(linkCopiedTimer);
      linkCopiedTimer = window.setTimeout(() => {
        linkEditor.copied = false;
        linkCopiedTimer = null;
      }, 1400);
    } catch {
      linkEditor.error = 'Der Link konnte nicht kopiert werden.';
    }
  }

  function handleEditorPaste(event) {
    const ed = editor.value;
    if (!ed || ed.state.selection.empty) return false;
    const raw = event.clipboardData?.getData('text/plain')?.trim() || '';
    const href = normalizeNoteHref(raw);
    if (!href) return false;
    event.preventDefault();
    ed.chain()
      .focus()
      .setLink({ href, target: '_blank', rel: 'noopener noreferrer' })
      .run();
    return true;
  }

  function handleEditorLinkClick(view, event) {
    const target = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!target) return false;
    event.preventDefault();
    try {
      const from = view.posAtDOM(target, 0);
      const to = view.posAtDOM(target, target.childNodes.length);
      editor.value?.commands.setTextSelection({ from, to });
      nextTick(() => openLinkEditor({ from, to, href: target.getAttribute('href') || '' }));
      return true;
    } catch {
      return false;
    }
  }

  overlays.register('link', closeLinkEditor);
  onBeforeUnmount(() => { if (linkCopiedTimer) window.clearTimeout(linkCopiedTimer); });
  watch(() => props.noteId, () => closeLinkEditor());

  return {
    editor,
    linkEditor,
    linkInputEl,
    openLinkEditor,
    closeLinkEditor,
    applyLink,
    removeLink,
    openLinkTarget,
    copyLinkTarget,
    handleEditorPaste,
    handleEditorLinkClick,
  };
}

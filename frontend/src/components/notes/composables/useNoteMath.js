import { computed, nextTick, reactive, ref, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';
import katex from 'katex';
import { NOTE_KATEX_OPTIONS } from '../nodes/noteMath.js';

/**
 * Formel-Editor: Bearbeiten einer angeklickten Formel bzw. Einfügen einer
 * neuen (inline oder als Block) mit KaTeX-Live-Vorschau.
 */
export function useNoteMath({ editor, surfaceEl, props, overlays, clampMenuLeft }) {
  const mathInputEl = ref(null);
  const mathEditor = reactive({
    open: false,
    mode: 'insert',
    type: 'blockMath',
    pos: null,
    range: { from: 0, to: 0 },
    latex: '',
    style: {},
  });

  const previewHtml = computed(() => {
    const latex = mathEditor.latex.trim();
    if (!latex) return '';
    return katex.renderToString(latex, {
      ...NOTE_KATEX_OPTIONS,
      displayMode: mathEditor.type === 'blockMath',
    });
  });

  function position(rect) {
    const surface = surfaceEl.value;
    if (!surface || !rect) return;
    const box = surface.getBoundingClientRect();
    mathEditor.style = {
      left: `${clampMenuLeft(rect.left - box.left, box.width, 380)}px`,
      top: `${rect.bottom - box.top + 6}px`,
    };
  }

  function show() {
    mathEditor.open = true;
    overlays.open('math');
    nextTick(() => {
      mathInputEl.value?.focus();
      mathInputEl.value?.select();
    });
  }

  /** Klick auf eine bestehende Formel. */
  function editMathNode(node, pos) {
    const ed = editor.value;
    if (!ed?.isEditable || props.readonly) return;
    mathEditor.mode = 'edit';
    mathEditor.type = node.type.name;
    mathEditor.pos = pos;
    mathEditor.latex = String(node.attrs.latex || '');
    const dom = ed.view.nodeDOM(pos);
    position(dom instanceof Element ? dom.getBoundingClientRect() : posToDOMRect(ed.view, pos, pos + 1));
    show();
  }

  /**
   * Neue Formel an der Auswahl. Ohne Typvorgabe: markierter Text innerhalb
   * eines Absatzes wird zur Inline-Formel, sonst entsteht ein Formelblock.
   */
  function openMathInsert(type = null) {
    const ed = editor.value;
    if (!ed?.isEditable) return;
    const { from, to, empty } = ed.state.selection;
    const selected = empty ? '' : ed.state.doc.textBetween(from, to, ' ');
    mathEditor.mode = 'insert';
    mathEditor.type = type || (selected && !selected.includes('\n') ? 'inlineMath' : 'blockMath');
    mathEditor.pos = null;
    mathEditor.range = { from, to };
    mathEditor.latex = selected;
    position(posToDOMRect(ed.view, from, to));
    show();
  }

  function closeMathEditor(restoreFocus = false) {
    if (!mathEditor.open) return;
    mathEditor.open = false;
    if (restoreFocus) nextTick(() => editor.value?.chain().focus().run());
  }

  function nodeAtEditPos(ed) {
    const node = mathEditor.pos == null ? null : ed.state.doc.nodeAt(mathEditor.pos);
    return node && node.type.name === mathEditor.type ? node : null;
  }

  function applyMath() {
    const ed = editor.value;
    if (!ed) return;
    const latex = mathEditor.latex.trim();
    if (mathEditor.mode === 'edit') {
      const node = nodeAtEditPos(ed);
      if (!node) { closeMathEditor(true); return; }
      if (!latex) { removeMath(); return; }
      ed.chain().focus()
        .command(({ tr }) => { tr.setNodeMarkup(mathEditor.pos, undefined, { ...node.attrs, latex }); return true; })
        .setTextSelection(mathEditor.pos + node.nodeSize)
        .run();
      closeMathEditor();
      return;
    }
    if (!latex) { closeMathEditor(true); return; }
    const max = ed.state.doc.content.size;
    const range = { from: Math.min(mathEditor.range.from, max), to: Math.min(mathEditor.range.to, max) };
    ed.chain().focus()
      .insertContentAt(range, { type: mathEditor.type, attrs: { latex } })
      .run();
    closeMathEditor();
  }

  function removeMath() {
    const ed = editor.value;
    const node = ed && nodeAtEditPos(ed);
    if (node) {
      ed.chain().focus().deleteRange({ from: mathEditor.pos, to: mathEditor.pos + node.nodeSize }).run();
    }
    closeMathEditor();
  }

  /** Inline ↔ Block umschalten (nur beim Einfügen). */
  function toggleMathType() {
    mathEditor.type = mathEditor.type === 'blockMath' ? 'inlineMath' : 'blockMath';
    nextTick(() => mathInputEl.value?.focus());
  }

  function onMathKeydown(event) {
    if (event.key === 'Escape') { event.preventDefault(); closeMathEditor(true); return; }
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      applyMath();
    }
  }

  overlays.register('math', () => { mathEditor.open = false; });
  watch(() => props.noteId, () => closeMathEditor());

  return {
    editor,
    mathEditor,
    mathInputEl,
    previewHtml,
    editMathNode,
    openMathInsert,
    closeMathEditor,
    applyMath,
    removeMath,
    toggleMathType,
    onMathKeydown,
  };
}

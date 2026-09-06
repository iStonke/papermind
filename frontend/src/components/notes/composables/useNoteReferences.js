import { computed, reactive, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';
import { targetGlyph } from '../mockData.js';

export function useNoteReferences({
  editor,
  surfaceEl,
  props,
  overlays,
  clampMenuLeft,
  getTargets,
}) {
  const picker = reactive({ open: false, mode: 'document', items: [], index: 0, style: {}, live: false, from: null, query: '', onPick: null });

  const filteredPicker = computed(() => {
    const q = picker.query.trim().toLowerCase();
    if (!q) return picker.items;
    return picker.items.filter(it =>
      it.label.toLowerCase().includes(q) || (it.hint || '').toLowerCase().includes(q));
  });

  function pickerHint() { return picker.mode === 'target' ? 'Verweisen auf' : 'Beleg wählen'; }
  function pickerChip(it) { return targetGlyph(it.type); }

  function positionPicker() {
    const ed = editor.value, surface = surfaceEl.value;
    if (!ed || !surface) return;
    const pos = ed.state.selection.from;
    const rect = posToDOMRect(ed.view, pos, pos);
    const box = surface.getBoundingClientRect();
    picker.style = {
      left: `${clampMenuLeft(rect.left - box.left, box.width)}px`,
      top: `${rect.bottom - box.top + 4}px`,
    };
  }

  function openPicker(mode, items, onPick) {
    picker.mode = mode; picker.items = items; picker.onPick = onPick;
    picker.live = false; picker.from = null; picker.query = ''; picker.index = 0;
    positionPicker(); picker.open = true;
    overlays.open('picker');
  }

  function pickItem(item) {
    if (!item) return;
    const ed = editor.value;
    const onPick = picker.onPick;
    // Live-Picker ([[): den getippten „[[query"-Text vor dem Einfügen entfernen.
    if (picker.live && picker.from != null && ed) {
      const to = ed.state.selection.from;
      ed.chain().focus().deleteRange({ from: picker.from, to }).run();
    }
    picker.open = false;
    onPick?.(item);
  }

  // [[-Trigger: erkennt „[[query" am Cursor und öffnet den Ziel-Picker live.
  function refreshWikiLink() {
    const ed = editor.value, surface = surfaceEl.value;
    if (!ed || !surface) return;
    const { $from, empty } = ed.state.selection;
    const closeLive = () => { if (picker.live) picker.open = false; };
    if (!empty) { closeLive(); return; }
    if (!$from.parent.isTextblock || $from.parent.type.name === 'codeBlock') { closeLive(); return; }

    const before = $from.parent.textBetween(0, $from.parentOffset, '￼', '￼');
    const m = /\[\[([^[\]]*)$/.exec(before);
    if (!m) { closeLive(); return; }

    const query = m[1];
    picker.mode = 'target';
    picker.items = getTargets();
    picker.live = true;
    picker.from = ed.state.selection.from - (query.length + 2);
    picker.query = query;
    picker.onPick = (item) =>
      ed.chain().focus().insertWikiLink({ targetType: item.type, targetId: item.id, label: item.label }).run();
    if (!picker.open) picker.index = 0;
    positionPicker();
    picker.open = true;
    overlays.open('picker');
  }

  function handlePickerKeydown(event) {
    if (picker.open) {
      const items = filteredPicker.value;
      if (items.length) {
        const n = items.length;
        if (event.key === 'ArrowDown') { picker.index = (picker.index + 1) % n; return true; }
        if (event.key === 'ArrowUp') { picker.index = (picker.index - 1 + n) % n; return true; }
        if (event.key === 'Enter' || event.key === 'Tab') { pickItem(items[picker.index]); return true; }
      }
      if (event.key === 'Escape') { picker.open = false; return true; }
      // Live-Picker: Tippen/Backspace fließt in den [[…]]-Text (Query wächst/schrumpft).
      return false;
    }

    return false;
  }
  function closePicker() { picker.open = false; }
  overlays.register('picker', closePicker);
  watch(() => props.noteId, closePicker);

  watch(filteredPicker, (r) => { if (picker.index >= r.length) picker.index = 0; });
  return {
    editor,
    picker,
    filteredPicker,
    pickerHint,
    pickerChip,
    openPicker,
    closePicker,
    pickItem,
    refreshWikiLink,
    handlePickerKeydown,
  };
}

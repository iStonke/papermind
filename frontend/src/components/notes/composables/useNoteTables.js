import { reactive, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';

export function useNoteTables({
  editor,
  surfaceEl,
  props,
  overlays,
  clampMenuLeft,
}) {
  const TABLE_PICKER_SIZE = 5;
  const TABLE_PICKER_CELLS = Object.freeze(
    Array.from({ length: TABLE_PICKER_SIZE ** 2 }, (_, index) => ({
      row: Math.floor(index / TABLE_PICKER_SIZE) + 1,
      col: (index % TABLE_PICKER_SIZE) + 1,
    })),
  );
  const tableMenu = reactive({
    open: false,
    mode: 'insert',
    rows: 3,
    cols: 3,
    withHeaderRow: true,
    withHeaderColumn: false,
    anchorPos: null,
    style: {},
  });
  const tableHandle = reactive({
    visible: false,
    style: {},
  });
  let hoveredTableWrapper = null;
  let activeTableWrapper = null;
  function positionTableMenu() {
    const ed = editor.value;
    const surface = surfaceEl.value;
    if (!ed || !surface) return;
    const pos = Math.min(tableMenu.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
    const rect = posToDOMRect(ed.view, pos, pos);
    const box = surface.getBoundingClientRect();
    tableMenu.style = {
      left: `${clampMenuLeft(rect.left - box.left, box.width, 286)}px`,
      top: `${rect.bottom - box.top + 4}px`,
    };
  }

  function tableWrapperAtSelection() {
    const ed = editor.value;
    if (!ed?.isActive('table')) return null;
    const domAtSelection = ed.view.domAtPos(ed.state.selection.from)?.node;
    const element = domAtSelection instanceof Element
      ? domAtSelection
      : domAtSelection?.parentElement;
    return element?.closest('.tableWrapper') || null;
  }

  function positionTableHandle(wrapper) {
    const surface = surfaceEl.value;
    if (!surface || !(wrapper instanceof Element)) return;
    const surfaceRect = surface.getBoundingClientRect();
    const tableRect = wrapper.getBoundingClientRect();
    const outsideLeft = tableRect.left - surfaceRect.left - 30;
    tableHandle.style = {
      left: `${outsideLeft >= 2 ? outsideLeft : tableRect.left - surfaceRect.left + 6}px`,
      top: `${tableRect.top - surfaceRect.top + 7}px`,
    };
    tableHandle.visible = true;
    activeTableWrapper = wrapper;
  }

  function refreshTableHandle() {
    const wrapper = hoveredTableWrapper || tableWrapperAtSelection();
    if (!wrapper || !surfaceEl.value?.contains(wrapper)) {
      tableHandle.visible = false;
      activeTableWrapper = null;
      return;
    }
    positionTableHandle(wrapper);
  }

  function trackTableHandle(event) {
    const target = event.target;
    if (!(target instanceof Element) || target.closest('.pm-table-handle, .pm-table-menu')) return;
    hoveredTableWrapper = target.closest('.tableWrapper');
    refreshTableHandle();
  }

  function clearHoveredTable() {
    hoveredTableWrapper = null;
    refreshTableHandle();
  }

  function openTableMenuFromHandle() {
    const ed = editor.value;
    const surface = surfaceEl.value;
    const wrapper = activeTableWrapper;
    if (!ed || !surface || !(wrapper instanceof Element)) return;

    // Keep the chosen cell (or cell range) when opening its own table menu.
    // Only a handle belonging to another table needs a new selection.
    if (tableWrapperAtSelection() !== wrapper) {
      const cellContent = wrapper.querySelector('th p, td p, th, td');
      if (cellContent) {
        const pos = ed.view.posAtDOM(cellContent, 0);
        ed.chain().focus().setTextSelection(pos).run();
      }
    }

    const surfaceRect = surface.getBoundingClientRect();
    const tableRect = wrapper.getBoundingClientRect();
    tableMenu.mode = 'edit';
    tableMenu.anchorPos = ed.state.selection.from;
    tableMenu.style = {
      left: `${clampMenuLeft(tableRect.left - surfaceRect.left + 4, surfaceRect.width, 286)}px`,
      top: `${tableRect.top - surfaceRect.top + 36}px`,
    };
    tableMenu.open = true;
    overlays.open('table');
  }

  function openTableMenu(requestedMode = null) {
    const ed = editor.value;
    if (!ed) return;
    const explicitMode = requestedMode === 'insert' || requestedMode === 'edit' ? requestedMode : null;
    tableMenu.mode = explicitMode || (ed.isActive('table') ? 'edit' : 'insert');
    tableMenu.rows = 3;
    tableMenu.cols = 3;
    tableMenu.withHeaderRow = true;
    tableMenu.withHeaderColumn = false;
    tableMenu.anchorPos = ed.state.selection.from;
    positionTableMenu();
    tableMenu.open = true;
    overlays.open('table');
  }

  function selectTableSize(rows, cols) {
    tableMenu.rows = Math.min(TABLE_PICKER_SIZE, Math.max(1, Number(rows) || 1));
    tableMenu.cols = Math.min(TABLE_PICKER_SIZE, Math.max(1, Number(cols) || 1));
  }

  function selectTableHeaderMode(mode) {
    tableMenu.withHeaderRow = mode !== 'column';
    tableMenu.withHeaderColumn = mode === 'column';
  }

  function insertTable(rows = tableMenu.rows, cols = tableMenu.cols) {
    const ed = editor.value;
    if (!ed) return;
    const anchorPos = Math.min(tableMenu.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
    tableMenu.open = false;
    const chain = ed.chain()
      .focus()
      .setTextSelection(anchorPos)
      .insertTable({
        rows: Math.max(1, Number(rows) || 1),
        cols: Math.max(1, Number(cols) || 1),
        withHeaderRow: tableMenu.withHeaderRow,
      });
    if (tableMenu.withHeaderColumn) chain.toggleHeaderColumn();
    chain.scrollIntoView().run();
  }

  function runTableCommand(action) {
    const ed = editor.value;
    if (!ed || !ed.isActive('table')) return;
    const chain = ed.chain().focus();
    const commands = {
      addRowAfter: () => chain.addRowAfter(),
      addColumnAfter: () => chain.addColumnAfter(),
      toggleHeaderRow: () => chain.toggleHeaderRow(),
      toggleHeaderColumn: () => chain.toggleHeaderColumn(),
      deleteRow: () => chain.deleteRow(),
      deleteColumn: () => chain.deleteColumn(),
      deleteTable: () => chain.deleteTable(),
    };
    tableMenu.open = false;
    commands[action]?.().run();
  }

  function handleTableKeydown(event) {
    if (tableMenu.open) {
      if (event.key === 'Escape') { tableMenu.open = false; return true; }
      if (tableMenu.mode === 'insert') {
        if (event.key === 'ArrowRight') { selectTableSize(tableMenu.rows, tableMenu.cols + 1); return true; }
        if (event.key === 'ArrowLeft') { selectTableSize(tableMenu.rows, tableMenu.cols - 1); return true; }
        if (event.key === 'ArrowDown') { selectTableSize(tableMenu.rows + 1, tableMenu.cols); return true; }
        if (event.key === 'ArrowUp') { selectTableSize(tableMenu.rows - 1, tableMenu.cols); return true; }
        if (event.key === 'Enter') { insertTable(); return true; }
      }
    }

    return false;
  }
  function closeTableMenu() { tableMenu.open = false; }
  overlays.register('table', closeTableMenu);
  watch(() => props.noteId, () => { closeTableMenu(); tableHandle.visible = false; hoveredTableWrapper = null; activeTableWrapper = null; });

  return {
    editor,
    TABLE_PICKER_CELLS,
    tableMenu,
    tableHandle,
    openTableMenu,
    closeTableMenu,
    openTableMenuFromHandle,
    refreshTableHandle,
    trackTableHandle,
    clearHoveredTable,
    selectTableSize,
    selectTableHeaderMode,
    insertTable,
    runTableCommand,
    handleTableKeydown,
  };
}

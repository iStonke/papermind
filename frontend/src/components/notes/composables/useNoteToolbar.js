import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { pageLayoutAtSelection } from '../nodes/pageLayout.js';
import { NOTE_PAGE_LAYOUT_COLUMNS } from '../../../utils/noteLayouts.js';
import { NOTE_CALLOUT_OPTIONS } from '../../../utils/noteCallouts.js';
import { menuItemsOf, nextMenuItem } from '../../../utils/noteMenuNavigation.js';
import { useToolbarRoving } from '../../../composables/useToolbarRoving.js';

export function useNoteToolbar({ editor, rootEl, props, runToolbar, beforeOpen, closeLinkEditor, closeTableMenu, onInsert, onOutsidePointer, documentsAvailable, targetsAvailable, imageUploading }) {
function toolbarActive(name, attrs) { return editor.value?.isActive(name, attrs); }
const toolbarEl = ref(null);
// Pfeiltasten-Navigation innerhalb der Formatierungsleiste (ARIA Toolbar Pattern):
// die Menü-Buttons werden zu einem einzigen Tab-Stopp gebündelt.
useToolbarRoving(toolbarEl);
const openMenu = ref(null); // 'block' | 'layout' | 'highlight' | 'insert' | 'blocks' | null
const toolbarCompact = ref(false);
const TOOLBAR_COMPACT_WIDTH = 520;

const blockStyleItems = [
  { key: 'paragraph', label: 'Fließtext' },
  { key: 'h2', label: 'Überschrift 2' },
  { key: 'h3', label: 'Überschrift 3' },
  { key: 'h4', label: 'Überschrift 4' },
  { key: 'blockquote', label: 'Zitat' },
  { key: 'codeBlock', label: 'Codeblock' },
];

const listStyleItems = [
  { key: 'bulletList', icon: 'mdi-format-list-bulleted', label: 'Aufzählung' },
  { key: 'orderedList', icon: 'mdi-format-list-numbered', label: 'Nummerierte Liste' },
  { key: 'taskList', icon: 'mdi-checkbox-blank-circle-outline', label: 'Aufgaben' },
];

const pageLayoutItems = NOTE_PAGE_LAYOUT_COLUMNS.map((columns) => ({
  columns,
  label: `${columns} ${columns === 1 ? 'Spalte' : 'Spalten'}`,
}));

const toolbarCalloutOptions = NOTE_CALLOUT_OPTIONS.filter(
  (option) => !['deadline', 'source'].includes(option.value),
);

const quickBlockItems = computed(() => ([
  ...(props.blockTemplates || []).map((template) => ({
    key: `saved-${template.id}`,
    label: template.name || template.title || 'Schnellblock',
    glyph: '▤',
    preset: {
      title: template.title || '',
      color: template.color || 'teal',
      fields: Array.isArray(template.fields) ? template.fields : [],
    },
  })),
]));

const insertItems = [
  { key: 'link', name: 'link', icon: 'mdi-link-variant', label: 'Hyperlink', action: 'link' },
  { key: 'wikiLink', glyph: '[[', label: 'Verweis', action: 'target' },
  { key: 'documentChip', icon: 'mdi-file-document-outline', label: 'Beleg verknüpfen', action: 'document' },
  { key: 'table', name: 'table', icon: 'mdi-table', label: 'Tabelle', action: 'table' },
  { key: 'image', icon: 'mdi-image-plus-outline', label: 'Bild einfügen', action: 'image', requiresNote: true },
  { key: 'horizontalRule', glyph: '―', label: 'Trennlinie' },
];

const overflowItems = computed(() => {
  const items = [];
  for (const item of insertItems) {
    if (item.requiresNote && !props.noteId) continue;
    items.push(item);
  }
  return items;
});

function insertItemDisabled(item) {
  if (item.key === 'image') return imageUploading();
  if (item.action === 'document') return !documentsAvailable();
  if (item.action === 'target') return !targetsAvailable();
  return false;
}

function isBlockActive(key) {
  if (key === 'paragraph') return Boolean(toolbarActive('paragraph'));
  if (['blockquote', 'codeBlock', 'bulletList', 'orderedList', 'taskList'].includes(key)) {
    return Boolean(toolbarActive(key));
  }
  const level = { h2: 2, h3: 3, h4: 4 }[key];
  return Boolean(toolbarActive('heading', { level }));
}

function toggleMenu(which) {
  beforeOpen();
  openMenu.value = openMenu.value === which ? null : which;
}

// ── Tastatur-Semantik der Menü-Buttons (ARIA Menu Button Pattern) ──────────────
// Jeder Gruppen-Button ist ein Menü-Trigger; das zugehörige Dropdown hat role="menu".
const MENU_DROPDOWN_IDS = {
  block: 'note-editor-menu-text',
  layout: 'note-editor-menu-layout',
  insert: 'note-editor-menu-insert',
  blocks: 'note-editor-menu-blocks',
};

// Pfeil-runter/-hoch auf dem Button öffnet das Menü und setzt den Fokus auf den
// ersten bzw. letzten Eintrag.
function openMenuFocus(which, position = 'first') {
  openMenu.value = which;
  nextTick(() => {
    const items = menuItemsOf(document.getElementById(MENU_DROPDOWN_IDS[which]));
    if (!items.length) return;
    (position === 'last' ? items[items.length - 1] : items[0]).focus();
  });
}

// Tastatur INNERHALB eines offenen Menüs: Pfeile/Pos1/Ende rollen die Einträge,
// Escape schließt und gibt den Fokus an den Trigger zurück, Tab schließt nur.
function onMenuKeydown(event) {
  const dropdown = event.currentTarget;
  if (event.key === 'Escape') {
    event.preventDefault();
    const trigger = dropdown.previousElementSibling;
    openMenu.value = null;
    nextTick(() => trigger?.focus?.());
    return;
  }
  if (event.key === 'Tab') {
    openMenu.value = null;
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  const items = menuItemsOf(dropdown);
  if (!items.length) return;
  const next = nextMenuItem(items, document.activeElement, event.key);
  if (!next) return;
  event.preventDefault();
  next.focus();
}

// ── Tastenkürzel-Übersicht ─────────────────────────────────────────────────────

function runBlockStyle(key) {
  openMenu.value = null;
  runToolbar(key);
}
function currentPageLayoutColumns() {
  const ed = editor.value;
  return ed ? pageLayoutAtSelection(ed.state)?.node.childCount || null : null;
}
function runPageLayout(columns) {
  openMenu.value = null;
  closeTableMenu();
  closeLinkEditor();
  const ed = editor.value;
  if (!ed) return;
  if (pageLayoutAtSelection(ed.state)) ed.commands.setPageLayoutColumns(columns);
  else ed.commands.insertPageLayout(columns);
  ed.commands.focus();
}
function insertAdjacentPageLayout(placement) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  ed.commands.insertPageLayoutAdjacent(placement);
  ed.commands.focus();
}
function removeCurrentPageLayout() {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  ed.commands.unsetPageLayout();
  ed.commands.focus();
}
function isTextHighlightActive(color) {
  return Boolean(editor.value?.isActive('highlight', { color }));
}
function applyTextHighlight(color) {
  openMenu.value = null;
  editor.value?.chain().focus().setNoteHighlight(color).run();
}
function removeTextHighlight() {
  openMenu.value = null;
  editor.value?.chain().focus().unsetNoteHighlight().run();
}
function runMenuItem(item) {
  openMenu.value = null;
  if (item.action) { onInsert(item.action); return; }
  runToolbar(item.key);
}

function runCalloutKind(kind) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  const chain = ed.chain().focus();
  if (ed.isActive('callout')) chain.setCalloutKind(kind).run();
  else chain.insertCallout(kind).run();
}

function runQuickBlock(item) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed || !item?.preset) return;
  ed.chain().focus().insertTemplateBox(item.preset).run();
}

function onToolbarOutsidePointer(event) {
  onOutsidePointer(event);
  if (openMenu.value && toolbarEl.value && !toolbarEl.value.contains(event.target)) {
    openMenu.value = null;
  }
}

let toolbarResizeObserver = null;
onMounted(() => {
  document.addEventListener('pointerdown', onToolbarOutsidePointer, true);
  if (rootEl.value && typeof ResizeObserver !== 'undefined') {
    toolbarResizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width || 0;
      if (width > 0) toolbarCompact.value = width < TOOLBAR_COMPACT_WIDTH;
    });
    toolbarResizeObserver.observe(rootEl.value);
  }
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onToolbarOutsidePointer, true);
  toolbarResizeObserver?.disconnect();
  toolbarResizeObserver = null;
});

return { toolbarEl, openMenu, toolbarCompact, blockStyleItems, listStyleItems, pageLayoutItems, toolbarCalloutOptions, quickBlockItems, overflowItems, insertItemDisabled, isBlockActive, toggleMenu, openMenuFocus, onMenuKeydown, runBlockStyle, currentPageLayoutColumns, runPageLayout, insertAdjacentPageLayout, removeCurrentPageLayout, isTextHighlightActive, applyTextHighlight, removeTextHighlight, runMenuItem, runCalloutKind, runQuickBlock, toolbarActive };
}

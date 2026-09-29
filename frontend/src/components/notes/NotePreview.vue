<!--
  NotePreview — read-only Darstellung einer Notiz (für die Papierkorb-Vorschau).
  Nutzt denselben TipTap-Kern wie der Editor, aber editable:false und ohne
  jegliche Bearbeitungs-Chrome. Lädt die volle Notiz (inkl. body_json) über den
  Store; das Backend liefert dafür auch gelöschte Notizen aus.
-->
<template>
  <div
    ref="rootEl"
    class="note-preview"
    :class="[
      { 'note-preview--compact': compact },
      { 'note-preview--dark': theme === 'dark' },
      `note-preview--spacing-${notesParagraphSpacing}`,
      `note-preview--font-${notesFontFamily}`,
      `note-preview--font-size-${notesFontSize}`,
      `note-preview--line-spacing-${notesLineSpacing}`,
      `note-preview--heading-spacing-${notesHeadingSpacing}`,
      `note-preview--block-spacing-${notesBlockSpacing}`,
    ]"
  >
    <div v-if="loading" class="note-preview__state" aria-live="polite">
      <v-progress-circular indeterminate color="primary" size="24" width="2" />
    </div>
    <div v-else-if="error" class="note-preview__state note-preview__state--error" role="alert">
      <v-icon size="22">mdi-alert-circle-outline</v-icon>
      <span>{{ error }}</span>
    </div>
    <article v-else class="note-preview__sheet" @click="onSheetClick">
      <template v-if="!compact">
        <div class="note-preview__eyebrow">Notiz · Nur-Lese-Vorschau</div>
        <h1 class="note-preview__title" :class="{ 'is-untitled': !title.trim() }">
          {{ title.trim() || 'Ohne Titel' }}
        </h1>
      </template>
      <editor-content :editor="editor" />
    </article>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { EditorContent, useEditor } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Typography from '@tiptap/extension-typography';
import TaskList from '@tiptap/extension-task-list';
import { NoteAIGeneration } from './extensions/aiGeneration.js';
import TaskItem from '@tiptap/extension-task-item';
import { TableKit } from '@tiptap/extension-table';
import { DocumentChip } from './nodes/documentChip.js';
import { OcrQuote } from './nodes/ocrQuote.js';
import { AiBlock } from './nodes/aiBlock.js';
import { WikiLink } from './nodes/wikiLink.js';
import { Callout } from './nodes/callout.js';
import { CollapsibleSection } from './nodes/collapsibleSection.js';
import { PaperMindDocument } from './nodes/noteDocument.js';
import { LayoutColumn, PageLayout } from './nodes/pageLayout.js';
import { NoteHighlight } from './nodes/noteHighlight.js';
import { TemplateBox, TemplateField } from './nodes/templateBox.js';
import { NoteImage } from './nodes/noteImage.js';
import { LearnMarker } from './extensions/learnMarker.js';
import { useNotesStore } from '../../stores/notes.js';
import { useSettingsStore } from '../../stores/settings.js';

const props = defineProps({
  noteId: { type: String, default: null },
  // Lernbereich: Notiz ohne Kopf, Marker (data-pm-id) hervorheben und anklickbar machen.
  compact: { type: Boolean, default: false },
  theme: { type: String, default: 'light', validator: (value) => ['light', 'dark'].includes(value) },
  markerStates: { type: Object, default: null }, // { [pmId]: 'open' | 'done' }
  currentPmId: { type: String, default: null },
});
const emit = defineEmits(['select-marker']);
const rootEl = ref(null);

const EMPTY_DOC = { type: 'doc', content: [{ type: 'paragraph' }] };
const notesStore = useNotesStore();
const settingsStore = useSettingsStore();
const title = ref('');
const bodyJson = ref(null);
const loading = ref(false);
const error = ref('');
const notesParagraphSpacing = computed(() => {
  const value = settingsStore.settingsDraft?.ui?.notes_paragraph_spacing;
  return ['compact', 'comfortable', 'spacious'].includes(value) ? value : 'comfortable';
});
const notesFontFamily = computed(() => {
  const value = settingsStore.settingsDraft?.ui?.notes_font_family;
  return ['sans', 'inter', 'source-sans', 'atkinson', 'serif', 'source-serif', 'mono'].includes(value)
    ? value
    : 'sans';
});
const noteSetting = (key, allowed, fallback) => computed(() => {
  const value = settingsStore.settingsDraft?.ui?.[key];
  return allowed.includes(value) ? value : fallback;
});
const notesFontSize = noteSetting('notes_font_size', ['small', 'medium', 'large'], 'medium');
const notesLineSpacing = noteSetting('notes_line_spacing', ['compact', 'comfortable', 'spacious'], 'comfortable');
const notesHeadingSpacing = noteSetting('notes_heading_spacing', ['compact', 'comfortable', 'spacious'], 'comfortable');
const notesBlockSpacing = noteSetting('notes_block_spacing', ['compact', 'comfortable', 'spacious'], 'comfortable');

const editor = useEditor({
  editable: false,
  content: EMPTY_DOC,
  extensions: [
    StarterKit.configure({
      document: false,
      heading: { levels: [1, 2, 3, 4] },
      link: {
        openOnClick: true,
        HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer' },
      },
    }),
    PageLayout,
    LayoutColumn,
    NoteHighlight,
    PaperMindDocument,
    Typography,
    TaskList,
    NoteAIGeneration,
    TaskItem.configure({ nested: true }),
    TableKit.configure({ table: { resizable: false, renderWrapper: true } }),
    DocumentChip,
    OcrQuote,
    AiBlock,
    WikiLink,
    Callout,
    CollapsibleSection,
    TemplateBox,
    TemplateField,
    NoteImage,
    LearnMarker,
  ],
  editorProps: { attributes: { class: 'pm-content pm-content--readonly' } },
});

let markerObserver = null;
let markerFrame = 0;
function scheduleDecorate() {
  if (markerFrame) return;
  markerFrame = setTimeout(() => {
    markerFrame = 0;
    decorateMarkers();
    if (needsScroll) { needsScroll = false; scrollToCurrent(false); }
  }, 0);
}
let needsScroll = true;
onMounted(() => {
  if (!rootEl.value || typeof MutationObserver === 'undefined') return;
  // Der Editor-DOM wird erst nach dem Laden eingehängt (und von ProseMirror ggf. neu geschrieben).
  markerObserver = new MutationObserver(scheduleDecorate);
  markerObserver.observe(rootEl.value, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-pm-id'] });
  scheduleDecorate();
});
onBeforeUnmount(() => {
  markerObserver?.disconnect();
  if (markerFrame) clearTimeout(markerFrame);
  editor.value?.destroy();
});

// Inhalt setzen, sobald Editor UND geladene Notiz bereit sind.
watch(
  [editor, bodyJson],
  ([ed, body]) => {
    if (ed && body) {
      ed.commands.setContent(body, { emitUpdate: false });
      needsScroll = true;
      nextTick(scheduleDecorate);
    }
  },
);

// --- Lernbereich: Marker hervorheben, aktuellen zentrieren, Klick → Sprung ---
function decorateMarkers() {
  const root = rootEl.value;
  if (!root || !props.markerStates) return;
  root.querySelectorAll('[data-pm-id]').forEach((el) => {
    const id = el.getAttribute('data-pm-id');
    const state = props.markerStates[id];
    el.classList.toggle('lm-open', state === 'open');
    el.classList.toggle('lm-done', state === 'done');
    el.classList.toggle('lm-current', !!props.currentPmId && id === props.currentPmId);
  });
}
function scrollToCurrent(smooth = true) {
  const root = rootEl.value;
  const el = root?.querySelector('.lm-current');
  if (!root || !el) return;
  const r = root.getBoundingClientRect();
  const e = el.getBoundingClientRect();
  const top = root.scrollTop + (e.top - r.top) - r.height / 2 + e.height / 2;
  root.scrollTo({ top: Math.max(0, top), behavior: smooth ? 'smooth' : 'auto' });
}
function onSheetClick(ev) {
  if (!props.markerStates) return;
  const el = ev.target?.closest?.('[data-pm-id]');
  const id = el?.getAttribute('data-pm-id');
  if (id && props.markerStates[id]) emit('select-marker', id);
}
watch(() => [props.markerStates, props.currentPmId], () => {
  nextTick(() => { decorateMarkers(); scrollToCurrent(true); });
}, { deep: true });

async function load() {
  if (!props.noteId) {
    title.value = '';
    bodyJson.value = EMPTY_DOC;
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const note = await notesStore.get(props.noteId);
    title.value = note?.title || '';
    bodyJson.value = note?.body_json || EMPTY_DOC;
  } catch {
    error.value = 'Die Notiz konnte nicht geladen werden.';
  } finally {
    loading.value = false;
  }
}

watch(() => props.noteId, load, { immediate: true });
</script>

<style scoped>
.note-preview {
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  justify-content: center;
  --note-preview-font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  --note-preview-font-size: 1.0625rem;
  --note-preview-line-height: 1.55;
  --note-preview-paragraph-gap: 0.25em;
  --note-preview-heading-before-gap: 1.75rem;
  --note-preview-block-gap: 1.75rem;
}

.note-preview--dark {
  --pm-text: oklch(0.94 0.008 235);
  --pm-muted: oklch(0.76 0.020 240);
  --pm-text-muted: oklch(0.76 0.020 240);
  --pm-divider: oklch(0.42 0.030 250);
  --pm-content-surface: oklch(0.225 0.028 252);
  --pm-app-surface: oklch(0.205 0.026 252);
  --pm-surface-soft: oklch(0.30 0.028 250);
  --pm-viewer-surface: oklch(0.215 0.028 252);
  --pm-accent-strong: oklch(0.80 0.10 200);
  background: oklch(0.265 0.030 250);
  color: var(--pm-text);
}

.note-preview--font-serif {
  --note-preview-font-family: Georgia, "Times New Roman", serif;
}

.note-preview--font-inter {
  --note-preview-font-family: "Inter Variable", "Helvetica Neue", Arial, sans-serif;
}

.note-preview--font-source-sans {
  --note-preview-font-family: "Source Sans 3 Variable", "Helvetica Neue", Arial, sans-serif;
}

.note-preview--font-atkinson {
  --note-preview-font-family: "Atkinson Hyperlegible Next Variable", "Helvetica Neue", Arial, sans-serif;
}

.note-preview--font-source-serif {
  --note-preview-font-family: "Source Serif 4 Variable", Georgia, "Times New Roman", serif;
}

.note-preview--font-mono {
  --note-preview-font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
}

.note-preview--spacing-compact {
  --note-preview-paragraph-gap: 0;
}

.note-preview--spacing-spacious {
  --note-preview-paragraph-gap: 0.75em;
}

.note-preview--font-size-small { --note-preview-font-size: 0.9375rem; }
.note-preview--font-size-large { --note-preview-font-size: 1.1875rem; }
.note-preview--line-spacing-compact { --note-preview-line-height: 1.35; }
.note-preview--line-spacing-spacious { --note-preview-line-height: 1.75; }
.note-preview--heading-spacing-compact { --note-preview-heading-before-gap: 1.25rem; }
.note-preview--heading-spacing-spacious { --note-preview-heading-before-gap: 2.25rem; }
.note-preview--block-spacing-compact { --note-preview-block-gap: 1.25rem; }
.note-preview--block-spacing-spacious { --note-preview-block-gap: 2.25rem; }

.note-preview__state {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--pm-muted);
  font-size: 0.86rem;
}
.note-preview__state--error { color: var(--pm-danger, #c84c4c); }

.note-preview__sheet {
  width: 100%;
  max-width: 720px;
  align-self: flex-start;
  padding: 32px clamp(20px, 5vw, 52px) 64px;
}

.note-preview--compact .note-preview__sheet { padding-top: 28px; }
.note-preview :deep(.pm-content .lm-open),
.note-preview :deep(.pm-content .lm-done),
.note-preview :deep(.pm-content .lm-current) {
  box-sizing: border-box;
  padding: 0.35em 0.8em 0.4em 1em;
  border-radius: 8px;
  overflow-wrap: anywhere;
  cursor: pointer;
  transition: background .18s, box-shadow .18s, opacity .18s;
}
.note-preview :deep(.lm-open) { box-shadow: inset 3px 0 0 color-mix(in oklab, var(--pm-accent, #0b7280) 45%, transparent); background: color-mix(in oklab, var(--pm-accent, #0b7280) 5%, transparent); }
.note-preview :deep(.lm-open:hover) { background: color-mix(in oklab, var(--pm-accent, #0b7280) 10%, transparent); }
.note-preview :deep(.lm-done) { opacity: .5; box-shadow: inset 3px 0 0 color-mix(in oklab, var(--pm-success, #2e7d4f) 60%, transparent); }
.note-preview :deep(.lm-current) { opacity: 1; box-shadow: inset 4px 0 0 var(--pm-accent, #0b7280); background: color-mix(in oklab, var(--pm-accent, #0b7280) 14%, transparent); }
.note-preview :deep(.pm-learn-partial.lm-open),
.note-preview :deep(.pm-learn-partial.lm-open:hover),
.note-preview :deep(.pm-learn-partial.lm-current) {
  background: transparent;
}
.note-preview :deep(.pm-learn-selection) {
  border-radius: 0.18em;
  background: color-mix(in oklab, var(--pm-accent, #0b7280) 24%, transparent);
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}

.note-preview__eyebrow {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--pm-accent-strong, #00555f);
  margin-bottom: 12px;
}

.note-preview__title {
  font-family: var(--note-preview-font-family);
  font-weight: 600;
  font-size: clamp(1.6rem, 3vw, 2.1rem);
  line-height: 1.14;
  letter-spacing: -0.01em;
  color: var(--pm-text, #0e181b);
  margin: 0 0 16px;
}
.note-preview__title.is-untitled { color: var(--pm-muted); font-style: italic; font-weight: 400; }

/* ── Fließtext (ProseMirror), read-only ──────────────────────────────────── */
.note-preview :deep(.pm-content) {
  outline: none;
  color: var(--pm-text, #0e181b);
  font-family: var(--note-preview-font-family);
  font-size: var(--note-preview-font-size);
  line-height: var(--note-preview-line-height);
}
.note-preview :deep(.pm-content > *) { margin-block: 0; }
.note-preview :deep(.pm-content > * + *) { margin-top: var(--note-preview-paragraph-gap); }
.note-preview :deep(.pm-content > * + :not(p)),
.note-preview :deep(.pm-content > :not(p) + *) {
  margin-top: var(--note-preview-block-gap);
}
.note-preview :deep([data-page-layout]) {
  display: grid;
  align-items: stretch;
  width: 100%;
}
.note-preview :deep([data-page-layout][data-columns="1"]) { grid-template-columns: minmax(0, 1fr); }
.note-preview :deep([data-page-layout][data-columns="2"]) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.note-preview :deep([data-page-layout][data-columns="3"]) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.note-preview :deep([data-page-layout][data-columns="4"]) { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.note-preview :deep([data-page-layout][data-columns="5"]) { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.note-preview :deep([data-layout-column]) {
  min-width: 0;
  padding: 2px clamp(10px, 1.5vw, 20px);
  overflow-wrap: anywhere;
}
.note-preview :deep([data-layout-column] + [data-layout-column]) {
  border-left: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 82%, transparent);
}
.note-preview :deep([data-layout-column]:first-child) { padding-left: 0; }
.note-preview :deep([data-layout-column]:last-child) { padding-right: 0; }
.note-preview :deep([data-layout-column] > *) { margin-block: 0; }
.note-preview :deep([data-layout-column] > * + *) { margin-top: var(--note-preview-paragraph-gap); }
.note-preview :deep([data-layout-column] > * + :not(p)),
.note-preview :deep([data-layout-column] > :not(p) + *) {
  margin-top: var(--note-preview-block-gap);
}
.note-preview :deep(mark.pm-text-highlight) {
  padding-inline: 0.06em;
  border-radius: 0.16em;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
.note-preview :deep(.pm-content h1) {
  font-family: inherit; font-weight: 600;
  font-size: 1.5rem; line-height: 1.2; letter-spacing: -0.01em; margin-top: 1.3em;
}
.note-preview :deep(.pm-content h2) {
  font-family: inherit; font-weight: 600;
  font-size: 1.25rem; line-height: 1.25; margin-top: 1.2em;
}
.note-preview :deep(.pm-content h3) { font-weight: 600; font-size: 1.06rem; margin-top: 1.1em; }
.note-preview :deep(.pm-content h4) { font-weight: 600; font-size: 0.98rem; margin-top: 1em; }
.note-preview :deep(.pm-content > :first-child),
.note-preview :deep([data-layout-column] > :first-child) {
  margin-top: 0;
}
.note-preview :deep(.pm-content > :not(hr) + :is(h1, h2, h3, h4, h5, h6)),
.note-preview :deep([data-layout-column] > :not(hr) + :is(h1, h2, h3, h4, h5, h6)) {
  margin-top: var(--note-preview-heading-before-gap);
}
.note-preview :deep(.pm-content ul),
.note-preview :deep(.pm-content ol) { padding-left: 1.4em; }
.note-preview :deep(.pm-content li) { margin: 0.2em 0; }
.note-preview :deep(.pm-content blockquote) {
  border-left: 2.5px solid var(--pm-accent, #006b75);
  padding-left: 0.9em; margin-left: 0; color: var(--pm-muted, #535e62); font-style: italic;
}
.note-preview :deep(.pm-content code) {
  font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 0.86em;
  background: rgba(var(--v-theme-primary, 0 107 117), 0.1);
  color: var(--pm-accent-strong, #00555f); padding: 1px 5px; border-radius: 5px;
}
.note-preview :deep(.pm-content pre) {
  background: var(--pm-viewer-surface, #eef2f4);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px; padding: 12px 14px; overflow-x: auto;
}
.note-preview :deep(.pm-content pre code) { background: none; color: inherit; padding: 0; }
.note-preview :deep(.pm-content hr) {
  border: 0; height: 1px; background: var(--pm-divider, #d8dfe1); margin: 1.4em 0;
}
.note-preview :deep(.pm-content a) {
  color: var(--pm-accent-strong, #00555f);
  cursor: pointer;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}
.note-preview :deep(.pm-content ul[data-type="taskList"]) { list-style: none; padding-left: 0.2em; }
.note-preview :deep(.pm-content ul[data-type="taskList"] li) { display: flex; gap: 0.55em; align-items: flex-start; }
.note-preview :deep(.pm-content ul[data-type="taskList"] li > label) {
  display: grid;
  place-items: center;
  height: 1.7em;
  margin: 0;
}
.note-preview :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]) {
  appearance: none;
  -webkit-appearance: none;
  width: 1.05rem;
  height: 1.05rem;
  margin: 0;
  border: 1.5px solid color-mix(in srgb, var(--pm-muted, #748084) 72%, transparent);
  border-radius: 50%;
  background: transparent;
  pointer-events: none;
}
.note-preview :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]:checked) {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='m4 8 2.5 2.5L12 5' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-position: center;
  background-size: 0.85rem 0.85rem;
  background-repeat: no-repeat;
}
.note-preview :deep(.pm-content .tableWrapper) {
  max-width: 100%;
  overflow-x: auto;
  border-radius: 9px;
}
.note-preview :deep(.pm-content table) {
  width: 100%;
  min-width: 360px;
  overflow: hidden;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 9px;
  table-layout: fixed;
}
.note-preview :deep(.pm-content th),
.note-preview :deep(.pm-content td) {
  min-width: 88px;
  padding: 8px 10px;
  border-right: 1px solid var(--pm-divider, #d8dfe1);
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  vertical-align: top;
}
.note-preview :deep(.pm-content th:last-child),
.note-preview :deep(.pm-content td:last-child) { border-right: 0; }
.note-preview :deep(.pm-content tr:last-child > *) { border-bottom: 0; }
.note-preview :deep(.pm-content th) {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, var(--pm-app-surface, #fff));
  color: var(--pm-text, #0e181b);
  font-weight: 680;
  text-align: left;
}
.note-preview :deep(.pm-content th > p),
.note-preview :deep(.pm-content td > p) { margin: 0; }

@media (max-width: 760px) {
  .note-preview :deep([data-page-layout]) { grid-template-columns: 1fr !important; }
  .note-preview :deep([data-layout-column]) {
    padding: 16px 0;
  }
  .note-preview :deep([data-layout-column]:first-child) { padding-top: 0; }
  .note-preview :deep([data-layout-column] + [data-layout-column]) {
    border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 82%, transparent);
    border-left: 0;
  }
}
</style>

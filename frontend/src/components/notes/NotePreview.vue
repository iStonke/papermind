<!--
  NotePreview — read-only Darstellung einer Notiz (für die Papierkorb-Vorschau).
  Nutzt denselben TipTap-Kern wie der Editor, aber editable:false und ohne
  jegliche Bearbeitungs-Chrome. Lädt die volle Notiz (inkl. body_json) über den
  Store; das Backend liefert dafür auch gelöschte Notizen aus.
-->
<template>
  <div
    class="note-preview"
    :class="[
      `note-preview--spacing-${notesParagraphSpacing}`,
      `note-preview--font-${notesFontFamily}`,
    ]"
  >
    <div v-if="loading" class="note-preview__state" aria-live="polite">
      <v-progress-circular indeterminate color="primary" size="24" width="2" />
    </div>
    <div v-else-if="error" class="note-preview__state note-preview__state--error" role="alert">
      <v-icon size="22">mdi-alert-circle-outline</v-icon>
      <span>{{ error }}</span>
    </div>
    <article v-else class="note-preview__sheet">
      <div class="note-preview__eyebrow">Notiz · Nur-Lese-Vorschau</div>
      <h1 class="note-preview__title" :class="{ 'is-untitled': !title.trim() }">
        {{ title.trim() || 'Ohne Titel' }}
      </h1>
      <editor-content :editor="editor" />
    </article>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { EditorContent, useEditor } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Typography from '@tiptap/extension-typography';
import TaskList from '@tiptap/extension-task-list';
import TaskItem from '@tiptap/extension-task-item';
import { TableKit } from '@tiptap/extension-table';
import { DocumentChip } from './nodes/documentChip.js';
import { OcrQuote } from './nodes/ocrQuote.js';
import { AiBlock } from './nodes/aiBlock.js';
import { WikiLink } from './nodes/wikiLink.js';
import { Callout } from './nodes/callout.js';
import { useNotesStore } from '../../stores/notes.js';
import { useSettingsStore } from '../../stores/settings.js';

const props = defineProps({
  noteId: { type: String, default: null },
});

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
  return ['sans', 'serif', 'mono'].includes(value) ? value : 'sans';
});

const editor = useEditor({
  editable: false,
  content: EMPTY_DOC,
  extensions: [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4] },
      link: {
        openOnClick: true,
        HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer' },
      },
    }),
    Typography,
    TaskList,
    TaskItem.configure({ nested: true }),
    TableKit.configure({ table: { resizable: false, renderWrapper: true } }),
    DocumentChip,
    OcrQuote,
    AiBlock,
    WikiLink,
    Callout,
  ],
  editorProps: { attributes: { class: 'pm-content pm-content--readonly' } },
});

onBeforeUnmount(() => editor.value?.destroy());

// Inhalt setzen, sobald Editor UND geladene Notiz bereit sind.
watch(
  [editor, bodyJson],
  ([ed, body]) => {
    if (ed && body) ed.commands.setContent(body, { emitUpdate: false });
  },
);

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
  --note-preview-paragraph-gap: 0.25em;
}

.note-preview--font-serif {
  --note-preview-font-family: Georgia, "Times New Roman", serif;
}

.note-preview--font-mono {
  --note-preview-font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
}

.note-preview--spacing-compact {
  --note-preview-paragraph-gap: 0;
}

.note-preview--spacing-spacious {
  --note-preview-paragraph-gap: 0.5em;
}

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
  font-size: 1.0625rem;
  line-height: 1.7;
}
.note-preview :deep(.pm-content > *) { margin-block: 0; }
.note-preview :deep(.pm-content > * + *) { margin-top: var(--note-preview-paragraph-gap); }
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
.note-preview :deep(.pm-content ul[data-type="taskList"] input) { accent-color: var(--pm-accent, #006b75); pointer-events: none; }
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
</style>

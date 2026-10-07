<!--
  NoteDocumentPane — PDF-Spalte der Split-Ansicht Notiz↔Dokument. Zeigt das mit
  der Notiz verknüpfte Dokument im Zitat-Modus: Textauswahl bietet die drei
  festen Lernmarkierungen (wichtig/Definition/unklar) und „In Notiz übernehmen".
  Sichtbar sind nur die Lernmarkierungen DIESER Notiz – die Lesemodus-
  Markierungen sind eine getrennte Ebene und bleiben hier ausgeblendet.
  Merkt sich pro Notiz die zuletzt angesehene Seite.
-->
<template>
  <section class="note-doc-pane" aria-label="Verknüpftes Dokument">
    <header class="note-doc-pane__bar">
      <v-icon size="15" class="note-doc-pane__icon" aria-hidden="true">mdi-file-document-outline</v-icon>
      <span class="note-doc-pane__title" :title="documentTitle">{{ documentTitle || 'Dokument' }}</span>
      <button
        type="button"
        class="note-doc-pane__btn"
        title="Im Lesemodus öffnen"
        aria-label="Im Lesemodus öffnen"
        @click="emit('open-reader')"
      >
        <v-icon size="16">mdi-book-open-page-variant-outline</v-icon>
      </button>
      <button
        v-if="closable"
        type="button"
        class="note-doc-pane__btn"
        title="Dokument ausblenden"
        aria-label="Dokument ausblenden"
        @click="emit('close')"
      >
        <v-icon size="16">mdi-close</v-icon>
      </button>
    </header>

    <PdfPreview
      ref="previewRef"
      :key="documentId"
      class="note-doc-pane__preview"
      :src="src"
      :target-page="initialPage"
      quote-mode
      :selection-colors="LEARN_HIGHLIGHT_COLORS"
      :annotations="highlightAnnotations"
      @loaded="onLoaded"
      @create-note-quote="onQuote"
      @create-annotation="onCreateHighlight"
      @update-annotation="onRecolorHighlight"
      @delete-annotation="onDeleteHighlight"
    />
  </section>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue';
import { authedUrl, getBaseUrl } from '../../api/client.js';
import {
  createNoteLearnHighlight,
  deleteNoteLearnHighlight,
  listNoteLearnHighlights,
  updateNoteLearnHighlight,
} from '../../api/noteLearnHighlights.js';
import { notifyError } from '../../stores/notifications.js';
import { LEARN_HIGHLIGHT_COLORS, learnHighlightByHex, learnHighlightByKey } from './learnHighlightColors.js';

const PdfPreview = defineAsyncComponent(() => import('../PdfPreview.vue'));

const props = defineProps({
  noteId: { type: String, default: '' },
  documentId: { type: String, required: true },
  documentTitle: { type: String, default: '' },
  closable: { type: Boolean, default: true },
});
const emit = defineEmits(['quote', 'close', 'open-reader', 'highlights-changed']);

const PAGE_STORAGE_KEY = 'pm-note-split-pages-v1';
const PAGE_STORAGE_LIMIT = 200;

const previewRef = ref(null);
const loaded = ref(false);
let pendingReveal = null;
let savePageTimer = null;

// Stabile URL nur aus der Dokument-ID (wie die Dokumentvorschau): das rotierende
// Datei-Token liest authedUrl nicht-reaktiv, sonst lüde das PDF bei jeder
// Token-Erneuerung neu.
const src = computed(() => {
  const base = String(getBaseUrl() || '').replace(/\/$/, '');
  return authedUrl(`${base}/api/documents/${props.documentId}/file?role=searchable`);
});

function readStoredPages() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PAGE_STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
}

function storedPageFor(noteId, documentId) {
  const entry = readStoredPages()[noteId];
  return entry?.doc === documentId && Number(entry.page) > 1 ? Number(entry.page) : null;
}

function storePage(page) {
  if (!props.noteId || !page) return;
  try {
    const pages = readStoredPages();
    delete pages[props.noteId];
    pages[props.noteId] = { doc: props.documentId, page };
    const keys = Object.keys(pages);
    for (const key of keys.slice(0, Math.max(0, keys.length - PAGE_STORAGE_LIMIT))) delete pages[key];
    window.localStorage.setItem(PAGE_STORAGE_KEY, JSON.stringify(pages));
  } catch (_) { /* Speicher blockiert – Seite wird dann nicht gemerkt */ }
}

// Nur beim Öffnen: die zuletzt angesehene Seite dieser Notiz.
const initialPage = ref(storedPageFor(props.noteId, props.documentId));

watch(() => [props.noteId, props.documentId], ([noteId, documentId]) => {
  loaded.value = false;
  initialPage.value = storedPageFor(noteId, documentId);
});

watch(() => previewRef.value?.currentPage, (page) => {
  if (!loaded.value || !page) return;
  clearTimeout(savePageTimer);
  savePageTimer = setTimeout(() => storePage(page), 400);
});

function onLoaded() {
  loaded.value = true;
  if (pendingReveal) {
    const request = pendingReveal;
    pendingReveal = null;
    // PdfPreview scrollt NACH dem loaded-Event (nextTick) noch zur Startseite –
    // den genauen Sprung daher erst im nächsten Task ausführen, sonst würde er
    // überschrieben.
    setTimeout(() => previewRef.value?.revealRegion?.({ ...request, smooth: false }), 0);
  }
}

function onQuote({ page, quote, rects } = {}) {
  const text = String(quote || '').trim();
  if (!text) return;
  emit('quote', { text, page: page || null, rects: Array.isArray(rects) && rects.length ? rects : null });
}

// ── Lernmarkierungen dieser Notiz ─────────────────────────────────────────────
const highlights = ref([]);
let highlightsRevision = 0;

// Für PdfPreview als gewöhnliche Highlight-Annotationen (Farbe = Bedeutung).
const highlightAnnotations = computed(() => highlights.value.map((highlight) => ({
  id: highlight.id,
  kind: 'highlight',
  page: highlight.page,
  rects: highlight.rects,
  quote: highlight.quote,
  color: learnHighlightByKey(highlight.color)?.hex || LEARN_HIGHLIGHT_COLORS[0].hex,
})));

async function loadHighlights() {
  const revision = ++highlightsRevision;
  if (!props.noteId || !props.documentId) {
    highlights.value = [];
    return;
  }
  try {
    const response = await listNoteLearnHighlights(props.noteId, props.documentId);
    if (revision === highlightsRevision) highlights.value = response.items || [];
  } catch (error) {
    if (revision === highlightsRevision) notifyError(error, 'Lernmarkierungen konnten nicht geladen werden.');
  }
}

watch(() => [props.noteId, props.documentId], loadHighlights, { immediate: true });

function changed() {
  emit('highlights-changed');
}

async function onCreateHighlight({ page, color, rects, quote } = {}) {
  const meaning = learnHighlightByHex(color);
  if (!props.noteId || !meaning || !page || !rects?.length) return;
  try {
    const created = await createNoteLearnHighlight(props.noteId, {
      document_id: props.documentId,
      page,
      color: meaning.key,
      rects,
      quote: quote || null,
    });
    highlights.value = [...highlights.value, created];
    changed();
  } catch (error) {
    notifyError(error, 'Lernmarkierung konnte nicht gespeichert werden.');
  }
}

async function onRecolorHighlight(highlightId, patch = {}) {
  const meaning = learnHighlightByHex(patch.color);
  if (!meaning) return;
  try {
    const updated = await updateNoteLearnHighlight(highlightId, meaning.key);
    highlights.value = highlights.value.map((item) => (item.id === updated.id ? updated : item));
    changed();
  } catch (error) {
    notifyError(error, 'Lernmarkierung konnte nicht geändert werden.');
  }
}

async function onDeleteHighlight(highlightId) {
  const previous = highlights.value;
  highlights.value = previous.filter((item) => item.id !== highlightId);
  try {
    await deleteNoteLearnHighlight(highlightId);
    changed();
  } catch (error) {
    highlights.value = previous;
    notifyError(error, 'Lernmarkierung konnte nicht entfernt werden.');
  }
}

/** Springt zur zitierten Stelle; vor dem Laden wird der Sprung vorgemerkt. */
function reveal(request) {
  if (!request?.page) return;
  if (!loaded.value || !previewRef.value?.revealRegion) {
    pendingReveal = request;
    // Startseite gleich passend setzen, statt erst die gemerkte Seite anzufahren.
    initialPage.value = Number(request.page) || initialPage.value;
    return;
  }
  previewRef.value.revealRegion(request);
}

onBeforeUnmount(() => {
  clearTimeout(savePageTimer);
  const page = previewRef.value?.currentPage;
  if (loaded.value && page) storePage(page);
});

defineExpose({ reveal, reloadHighlights: loadHighlights });
</script>

<style scoped>
.note-doc-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: var(--pm-viewer-surface, rgb(var(--v-theme-surface)));
}

.note-doc-pane__bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  height: 38px;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.note-doc-pane__icon {
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.note-doc-pane__title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.note-doc-pane__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: rgba(var(--v-theme-on-surface), 0.6);
  cursor: pointer;
}

.note-doc-pane__btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.07);
  color: rgba(var(--v-theme-on-surface), 0.88);
}

.note-doc-pane__preview {
  flex: 1 1 auto;
  min-height: 0;
}
</style>

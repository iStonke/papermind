<!--
  NoteDocumentPane — Dokumentansicht innerhalb der Notizen. Zeigt das mit
  der Notiz verknüpfte Dokument im Zitat-Modus: Textauswahl bietet die drei
  festen Lernmarkierungen (wichtig/Definition/unklar) und „In Notiz übernehmen".
  Sichtbar sind nur die Lernmarkierungen DIESER Notiz – die Lesemodus-
  Markierungen sind eine getrennte Ebene und bleiben hier ausgeblendet.
  Merkt sich pro Notiz die zuletzt angesehene Seite.
-->
<template>
  <section class="note-doc-pane" aria-label="Verknüpftes Dokument">
    <PdfPreview
      ref="previewRef"
      :key="documentId"
      class="note-doc-pane__preview"
      :src="src"
      :target-page="initialPage"
      quote-mode
      enable-document-list
      enable-unlink-document
      @unlink-document="emit('unlink-document')"
      @open-document-list="emit('open-document-list')"
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
const emit = defineEmits(['unlink-document', 'open-document-list', 'quote', 'close', 'open-reader', 'highlights-changed']);

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

function rectsOverlap(a, b) {
  const epsilon = 0.002;
  return a.x < b.x + b.w + epsilon && b.x < a.x + a.w + epsilon
    && a.y < b.y + b.h + epsilon && b.y < a.y + a.h + epsilon;
}

// Lernmarkierung dieser Notiz, die die Auswahl berührt (für den Lern-Marker
// des übernommenen Zitats). Bei mehreren gewinnt die zuletzt angelegte.
function highlightUnder(page, rects) {
  if (!page || !rects?.length) return null;
  const hits = highlights.value.filter((highlight) => highlight.page === page
    && (highlight.rects || []).some((own) => rects.some((sel) => rectsOverlap(own, sel))));
  return hits[hits.length - 1] || null;
}

function onQuote({ page, quote, rects } = {}) {
  const text = String(quote || '').trim();
  if (!text) return;
  const cleanRects = Array.isArray(rects) && rects.length ? rects : null;
  emit('quote', { text, page: page || null, rects: cleanRects });
}

// „Unklar" übernimmt die Stelle sofort als offene Frage (Lern-Marker) in die
// Notiz – so landet sie ohne weiteren Schritt in der Nachbereitung.
function autoQuote(highlight) {
  const meaning = learnHighlightByKey(highlight?.color);
  const text = String(highlight?.quote || '').trim();
  if (!meaning?.autoQuote || !text) return;
  emit('quote', {
    text,
    page: highlight.page,
    rects: highlight.rects,
    learnKind: meaning.markerKind,
    auto: true,
  });
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
    autoQuote(created);
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
    autoQuote(updated);
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
  box-sizing: border-box;
  background: var(--pm-viewer-surface, rgb(var(--v-theme-surface)));
}

.note-doc-pane__preview {
  flex: 1 1 auto;
  min-height: 0;
}
</style>

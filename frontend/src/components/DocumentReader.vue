<template>
  <Teleport to="body">
    <Transition name="reader" appear @after-leave="$emit('close')">
    <div
      v-if="!leaving"
      class="doc-reader"
      :class="{ 'doc-reader--light': readerTheme === 'light' }"
      role="dialog"
      aria-modal="true"
      :aria-label="`Lesemodus: ${title || 'Dokument'}`"
    >
      <!-- Kopfleiste -->
      <header class="doc-reader__bar">
        <div class="doc-reader__bar-left">
          <button class="doc-reader__icon-btn" aria-label="Lesemodus schließen" title="Schließen (Esc)" @click="requestClose">
            <v-icon size="20">mdi-arrow-collapse</v-icon>
          </button>
          <div class="doc-reader__title-wrap">
            <div class="doc-reader__title" :title="title">{{ title || 'Dokument' }}</div>
            <div
              v-if="metaParts.length"
              class="doc-reader__title-meta"
              :title="metaParts.join(' · ')"
            >
              <template v-for="(part, index) in metaParts" :key="`${part}-${index}`">
                <span class="doc-reader__title-meta-part">{{ part }}</span>
                <span
                  v-if="index < metaParts.length - 1"
                  class="doc-reader__title-meta-dot"
                  aria-hidden="true"
                />
              </template>
            </div>
          </div>
        </div>
        <div class="doc-reader__bar-actions">
          <div class="doc-reader__view-toggle" role="group" aria-label="Ansicht">
            <button
              class="doc-reader__icon-btn"
              :aria-pressed="readerTheme === 'light'"
              :aria-label="readerTheme === 'light' ? 'Dunklen Lesemodus aktivieren' : 'Hellen Lesemodus aktivieren'"
              :title="readerTheme === 'light' ? 'Dunkle Ansicht' : 'Helle Ansicht'"
              @click="toggleReaderTheme"
            >
              <v-icon size="20">{{ readerTheme === 'light' ? 'mdi-weather-night' : 'mdi-weather-sunny' }}</v-icon>
            </button>
            <span class="doc-reader__view-divider" role="separator" aria-hidden="true" />
            <button
              class="doc-reader__icon-btn"
              :class="{ 'doc-reader__icon-btn--active': showThumbs }"
              :aria-pressed="showThumbs"
              aria-label="Miniaturen umschalten"
              title="Miniaturen"
              @click="toggleThumbs"
            >
              <v-icon size="20">mdi-view-grid-outline</v-icon>
            </button>
            <button
              class="doc-reader__icon-btn"
              :class="{ 'doc-reader__icon-btn--active': showTools }"
              :aria-pressed="showTools"
              aria-label="Werkzeuge ein- oder ausblenden"
              title="Werkzeuge"
              @click="showTools = !showTools"
            >
              <v-icon size="20">mdi-toolbox-outline</v-icon>
            </button>
            <button
              class="doc-reader__icon-btn"
              :class="{ 'doc-reader__icon-btn--active': showNotes }"
              :aria-pressed="showNotes"
              aria-label="Kommentar ein- oder ausblenden"
              title="Kommentar"
              @click="showNotes = !showNotes"
            >
              <v-icon size="20">mdi-comment-text-outline</v-icon>
              <span v-if="noteAnnotations.length" class="doc-reader__badge">{{ noteAnnotations.length }}</span>
            </button>
          </div>
        </div>
      </header>

      <div class="doc-reader__body">
        <!-- Miniatur-Leiste -->
        <aside
          ref="railEl"
          class="doc-reader__rail"
          :class="{ 'doc-reader__rail--hidden': !showThumbs }"
          :aria-hidden="!showThumbs"
          :inert="!showThumbs"
          aria-label="Seitenminiaturen"
        >
          <button
            v-for="page in pageTotal"
            :key="page"
            :ref="el => setThumbRef(el, page)"
            class="doc-reader__thumb"
            :class="{ 'doc-reader__thumb--active': page === currentPage }"
            :data-page="page"
            :aria-label="`Zu Seite ${page} springen`"
            :aria-current="page === currentPage ? 'true' : undefined"
            @click="goToPage(page)"
          >
            <canvas :ref="el => setCanvasRef(el, page)" class="doc-reader__thumb-canvas" />
            <span class="doc-reader__thumb-num">{{ page }}</span>
          </button>
        </aside>

        <!-- Hauptansicht: dieselbe PdfPreview, voller Platz -->
        <main class="doc-reader__main">
          <PdfPreview
            ref="previewRef"
            :src="src"
            :target-page="targetPage"
            :annotatable="true"
            :annotation-tool="showTools ? activeTool : ''"
            :annotation-color="activeColor"
            :annotations="annotations"
            @loaded="onPreviewLoaded"
            @create-annotation="$emit('create-annotation', $event)"
            @delete-annotation="$emit('delete-annotation', $event)"
            @update-annotation="(...args) => $emit('update-annotation', ...args)"
            @request-link="$emit('request-link', $event)"
            @request-comment="onRequestComment"
          />
        </main>

        <!-- Werkzeug-Leiste -->
        <aside
          class="doc-reader__tools"
          :class="{ 'doc-reader__tools--hidden': !showTools }"
          :aria-hidden="!showTools"
          :inert="!showTools"
          aria-label="Werkzeuge"
        >
          <button
            v-for="tool in readerTools"
            :key="tool.id"
            class="doc-reader__tool-btn"
            :class="{ 'doc-reader__tool-btn--active': activeTool === tool.id }"
            :aria-label="tool.label"
            :aria-pressed="activeTool === tool.id"
            :title="tool.label"
            @click="activeTool = tool.id"
          >
            <v-icon size="20">{{ tool.icon }}</v-icon>
          </button>

          <!-- Universelle Farbwahl: gilt für Rechteck/Stift/Text, nur bei diesen sichtbar -->
          <template v-if="usesDrawColor">
            <div class="doc-reader__tool-divider" role="separator" />
            <button
              v-for="c in drawColors"
              :key="c"
              class="doc-reader__color-btn"
              :class="{ 'doc-reader__color-btn--active': activeColor === c }"
              :style="{ '--swatch-color': c }"
              :aria-label="`Farbe wählen: ${c}`"
              :aria-pressed="activeColor === c"
              @click="activeColor = c"
            />
          </template>
        </aside>

        <!-- Kommentar-Leiste -->
        <aside
          class="doc-reader__notes"
          :class="{ 'doc-reader__notes--hidden': !showNotes }"
          :aria-hidden="!showNotes"
          :inert="!showNotes"
          aria-label="Kommentare"
        >
          <div class="doc-reader__notes-head">
            <span>Kommentare</span>
            <span class="doc-reader__notes-count">{{ noteAnnotations.length }}</span>
          </div>

          <div v-if="!noteAnnotations.length" class="doc-reader__notes-empty">
            <strong>Keine Kommentare</strong>
            <span>Markiere Text im Dokument und wähle im Auswahlmenü das Kommentar-Symbol.</span>
          </div>

          <TransitionGroup v-else tag="ul" name="note" class="doc-reader__notes-list">
            <li
              v-for="annot in sortedNoteAnnotations"
              :key="annot.id"
              class="doc-reader__note"
              :style="{ '--note-color': annot.color || '#FAC775' }"
            >
              <button class="doc-reader__note-jump" :aria-label="`Zu Seite ${annot.page} springen`" @click="goToPage(annot.page)">
                <span class="doc-reader__note-main">
                  <span class="doc-reader__note-dot" aria-hidden="true" />
                  <span class="doc-reader__note-quote">{{ annot.quote || '(ohne Text)' }}</span>
                </span>
                <span class="doc-reader__note-page">S. {{ annot.page }}</span>
              </button>

              <button
                v-if="annot.kind === 'link'"
                class="doc-reader__note-link"
                :aria-label="`Verknüpftes Dokument öffnen: ${annot.target_document_title || ''}`"
                @click="$emit('open-link', annot)"
              >
                <v-icon size="14">mdi-link-variant</v-icon>
                <span class="doc-reader__note-link-title">{{ annot.target_document_title || 'Verknüpftes Dokument' }}</span>
                <v-icon size="14" class="doc-reader__note-link-go">mdi-chevron-right</v-icon>
              </button>

              <div v-if="editingId === annot.id" class="doc-reader__note-edit">
                <textarea
                  ref="editFieldEl"
                  v-model="editingText"
                  class="doc-reader__note-input"
                  rows="2"
                  placeholder="Kommentar…"
                  @keydown.enter.exact.prevent="commitEdit(annot)"
                  @keydown.esc.prevent="cancelEdit"
                />
                <div class="doc-reader__note-edit-actions">
                  <button class="doc-reader__note-btn" @click="commitEdit(annot)">Speichern</button>
                  <button class="doc-reader__note-btn doc-reader__note-btn--ghost" @click="cancelEdit">Abbrechen</button>
                </div>
              </div>
              <button
                v-else
                class="doc-reader__note-comment"
                :class="{ 'doc-reader__note-comment--empty': !annot.comment }"
                @click="startEdit(annot)"
              >
                {{ annot.comment || 'Kommentar hinzufügen…' }}
              </button>

              <button class="doc-reader__note-delete" aria-label="Markierung löschen" title="Löschen" @click="$emit('delete-annotation', annot.id)">
                <v-icon size="16">mdi-trash-can-outline</v-icon>
              </button>
            </li>
          </TransitionGroup>
        </aside>
      </div>
    </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import PdfPreview from './PdfPreview.vue';

const props = defineProps({
  src:         { type: String, default: '' },
  targetPage:  { type: Number, default: null },
  annotations: { type: Array, default: () => [] },
  title:       { type: String, default: '' },
  metaParts:   { type: Array, default: () => [] },
  editAnnotationId: { type: [String, Number], default: null },
});

const emit = defineEmits(['close', 'create-annotation', 'delete-annotation', 'update-annotation', 'request-link', 'open-link']);

const previewRef = ref(null);
const railEl = ref(null);
const editFieldEl = ref(null);

const READER_TOGGLE_STORAGE_KEY = 'papermind.reader.viewToggles.v1';

function readStoredToggles() {
  if (typeof window === 'undefined') return {};
  try {
    const parsed = JSON.parse(window.localStorage.getItem(READER_TOGGLE_STORAGE_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
}

const storedToggles = readStoredToggles();

const showThumbs = ref(typeof storedToggles.thumbs === 'boolean' ? storedToggles.thumbs : true);
const showNotes = ref(typeof storedToggles.notes === 'boolean' ? storedToggles.notes : true);
const showTools = ref(typeof storedToggles.tools === 'boolean' ? storedToggles.tools : false);
// Eigenständige Lesemodus-Optik (unabhängig vom App-Theme): dunkel als Voreinstellung.
const readerTheme = ref(storedToggles.theme === 'light' ? 'light' : 'dark');
const pageTotal = ref(0);
const leaving = ref(false); // steuert die Leave-Transition vor dem Schließen

const editingId = ref(null);
const editingText = ref('');
const handledEditAnnotationId = ref(null);
const activeTool = ref('highlight');

const readerTools = [
  { id: 'text', label: 'Text', icon: 'mdi-format-text' },
  { id: 'highlight', label: 'Hervorheben', icon: 'mdi-format-color-highlight' },
  { id: 'rectangle', label: 'Rechteck', icon: 'mdi-rectangle-outline' },
  { id: 'pen', label: 'Stift', icon: 'mdi-pencil-outline' },
  { id: 'eraser', label: 'Radierer', icon: 'mdi-eraser' },
];

// Universelle Farbwahl: eine gemeinsame Farbe für Rechteck/Stift/Text statt
// je Werkzeug eine feste Farbe. Nur relevant/sichtbar bei diesen 3 Werkzeugen.
const drawColors = ['#0F172A', '#DC2626', '#EA580C', '#16A34A', '#0EA5E9', '#7C3AED'];
const activeColor = ref(drawColors[4]);
const usesDrawColor = computed(() => ['rectangle', 'pen', 'text'].includes(activeTool.value));

// Aktuelle Seite aus der (exposeten) PdfPreview – reaktiv für Rail-Hervorhebung.
const currentPage = computed(() => previewRef.value?.currentPage || 1);

const noteAnnotations = computed(() =>
  props.annotations.filter((annot) => annot.kind === 'note' || annot.kind === 'link' || Boolean(annot.comment)),
);

const sortedNoteAnnotations = computed(() =>
  [...noteAnnotations.value].sort((a, b) => (a.page - b.page) || (a.created_at < b.created_at ? -1 : 1)),
);

// ── Miniaturen ────────────────────────────────────────────────────────────────
const thumbEls = new Map();   // page → button-Element
const canvasEls = new Map();  // page → canvas-Element
const renderedThumbs = new Set();
let thumbObserver = null;

function setThumbRef(el, page) {
  if (el) thumbEls.set(page, el);
  else thumbEls.delete(page);
}
function setCanvasRef(el, page) {
  if (el) {
    canvasEls.set(page, el);
    return;
  }
  canvasEls.delete(page);
  renderedThumbs.delete(page);
}

function renderVisibleThumbs() {
  const rail = railEl.value;
  if (!rail) return;
  const railRect = rail.getBoundingClientRect();
  for (const [page, thumb] of thumbEls.entries()) {
    const rect = thumb.getBoundingClientRect();
    if (rect.bottom >= railRect.top - 300 && rect.top <= railRect.bottom + 300) {
      renderThumb(page);
    }
  }
}

function setupThumbObserver() {
  thumbObserver?.disconnect();
  if (!railEl.value) return;
  thumbObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const page = Number(entry.target.dataset.page);
        renderThumb(page);
      }
    },
    { root: railEl.value, rootMargin: '300px 0px', threshold: 0 },
  );
  for (const el of thumbEls.values()) thumbObserver.observe(el);
  renderVisibleThumbs();
}

async function renderThumb(page) {
  if (renderedThumbs.has(page)) return;
  const canvas = canvasEls.get(page);
  const api = previewRef.value;
  if (!canvas || !api?.renderThumbnail) return;
  renderedThumbs.add(page);
  try {
    await api.renderThumbnail(page, canvas);
    canvas.style.opacity = '1'; // sanftes Einblenden nach dem Rendern
  } catch (error) {
    renderedThumbs.delete(page);
    console.warn('Miniatur konnte nicht gerendert werden:', error);
  }
}

async function onPreviewLoaded() {
  pageTotal.value = previewRef.value?.pageCount || 0;
  renderedThumbs.clear();
  await nextTick();
  setupThumbObserver();
}

function goToPage(page) {
  previewRef.value?.goToPage(page);
  // Aktive Miniatur in den sichtbaren Bereich rollen.
  nextTick(() => thumbEls.get(page)?.scrollIntoView({ block: 'nearest' }));
}

function toggleThumbs() {
  showThumbs.value = !showThumbs.value;
  if (showThumbs.value) nextTick(() => renderVisibleThumbs());
}

// ── Notiz-Kommentar bearbeiten ──────────────────────────────────────────────
function startEdit(annot) {
  editingId.value = annot.id;
  editingText.value = annot.comment || '';
  nextTick(() => {
    const field = Array.isArray(editFieldEl.value) ? editFieldEl.value[0] : editFieldEl.value;
    field?.focus();
  });
}

function openAnnotationEditor(annot, { markHandled = false } = {}) {
  if (!annot?.id) return;
  if (markHandled) handledEditAnnotationId.value = annot.id;
  showNotes.value = true;
  if (annot.page) goToPage(annot.page);
  startEdit(annot);
}

function onRequestComment(draft) {
  if (!draft) return;
  showNotes.value = true;
  emit('create-annotation', {
    page: draft.page,
    kind: 'note',
    color: draft.color || '#FAC775',
    rects: draft.rects,
    quote: draft.quote,
    comment: null,
    _afterCreate: (created) => {
      if (!created) return;
      nextTick(() => openAnnotationEditor(created, { markHandled: true }));
    },
  });
}

watch(
  [() => props.editAnnotationId, () => props.annotations],
  ([requestedId]) => {
    if (!requestedId || requestedId === handledEditAnnotationId.value) return;
    const annot = props.annotations.find((item) => item.id === requestedId);
    if (!annot) return;
    nextTick(() => openAnnotationEditor(annot, { markHandled: true }));
  },
  { immediate: true },
);

watch([showThumbs, showNotes, showTools, readerTheme], ([thumbs, notes, tools, theme]) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(
    READER_TOGGLE_STORAGE_KEY,
    JSON.stringify({ thumbs, notes, tools, theme }),
  );
});

function toggleReaderTheme() {
  readerTheme.value = readerTheme.value === 'light' ? 'dark' : 'light';
}

function cancelEdit() {
  editingId.value = null;
  editingText.value = '';
}
function commitEdit(annot) {
  const next = editingText.value.trim();
  if (next !== (annot.comment || '')) {
    emit('update-annotation', annot.id, { comment: next || null });
  }
  cancelEdit();
}

function requestClose() {
  // Löst die Leave-Transition aus; @after-leave emittiert dann 'close'.
  if (!leaving.value) leaving.value = true;
}

function onKeydown(event) {
  if (event.key === 'Escape' && editingId.value === null) {
    requestClose();
  }
}

onMounted(() => {
  document.documentElement.style.overflow = 'hidden';
  window.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => {
  thumbObserver?.disconnect();
  document.documentElement.style.overflow = '';
  window.removeEventListener('keydown', onKeydown);
});
</script>

<style scoped>
/* Lesemodus fährt wie eine Schublade von unten hoch und schließt nach unten. */
.reader-enter-active {
  transition: transform 460ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.reader-leave-active {
  transition: transform 620ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}
.reader-enter-from,
.reader-leave-to {
  transform: translateY(100%);
}
.reader-enter-to,
.reader-leave-from {
  transform: translateY(0);
}
@media (prefers-reduced-motion: reduce) {
  .reader-enter-active,
  .reader-leave-active,
  .doc-reader__rail,
  .doc-reader__tools,
  .doc-reader__notes,
  .note-enter-active,
  .note-leave-active,
  .note-move,
  .doc-reader__thumb-canvas {
    transition: none;
  }
}

.doc-reader {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  flex-direction: column;

  /* Dunkle Voreinstellung. Alle Flächen/Trenner laufen über diese Tokens,
     damit die helle Variante nur die Werte umschalten muss. */
  --reader-bg: rgb(8 13 23);
  --reader-panel-bg: rgb(12 18 30);
  --reader-panel-bg-soft: rgb(15 22 36);
  --reader-bar-bg: rgb(10 16 27 / 0.96);
  --reader-input-bg: rgb(8 13 23);
  --reader-text: rgb(241 245 249);
  --reader-text-rgb: 241 245 249;
  --reader-muted: rgb(226 232 240 / 0.62);
  --reader-muted-rgb: 226 232 240;
  /* Grund-Ton für durchscheinende Overlays (Hover/Ränder/Chips). */
  --reader-overlay-rgb: 255 255 255;
  --reader-divider: rgb(var(--reader-overlay-rgb) / 0.08);
  --reader-page-shadow: rgb(0 0 0 / 0.3);
  --reader-thumb-shadow: rgb(0 0 0 / 0.22);
  --reader-thumb-num-bg: rgb(15 23 42 / 0.72);

  background: var(--reader-bg);
  color: var(--reader-text);
}

.doc-reader--light {
  --reader-bg: #eef2f8;
  --reader-panel-bg: #f1f4fa;
  --reader-panel-bg-soft: #e9eef5;
  --reader-bar-bg: rgb(247 249 252 / 0.96);
  --reader-input-bg: #ffffff;
  --reader-text: #0f172a;
  --reader-text-rgb: 15 23 42;
  --reader-muted: rgb(51 65 85 / 0.72);
  --reader-muted-rgb: 51 65 85;
  --reader-overlay-rgb: 15 23 42;
  --reader-divider: rgb(var(--reader-overlay-rgb) / 0.1);
  --reader-page-shadow: rgb(15 23 42 / 0.14);
  --reader-thumb-shadow: rgb(15 23 42 / 0.12);
  --reader-thumb-num-bg: rgb(15 23 42 / 0.6);
}

.doc-reader__bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 54px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--reader-divider);
  background: var(--reader-bar-bg);
}

.doc-reader__bar-left {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.doc-reader__title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  max-width: 100%;
}

.doc-reader__title {
  flex: 0 1 auto;
  min-width: 4rem;
  font-size: 0.95rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--reader-text);
}

.doc-reader__title-meta {
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--reader-muted);
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
}

.doc-reader__title-meta-part {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-reader__title-meta-dot {
  width: 3px;
  height: 3px;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.7;
  flex: 0 0 auto;
}

.doc-reader__bar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.doc-reader__view-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.doc-reader__view-divider {
  width: 1px;
  height: 20px;
  background: var(--reader-divider);
}

.doc-reader__icon-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: rgb(var(--reader-muted-rgb) / 0.78);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease, transform 120ms ease;
}
.doc-reader__icon-btn:hover {
  background: rgb(var(--reader-overlay-rgb) / 0.07);
  color: var(--reader-text);
}
.doc-reader__icon-btn:active {
  transform: scale(0.94);
}
.doc-reader__icon-btn--active {
  background: rgb(var(--reader-overlay-rgb) / 0.08);
  border-color: rgb(var(--reader-overlay-rgb) / 0.1);
  color: var(--reader-text);
}
.doc-reader__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  border: 1px solid var(--reader-bg);
  background: rgb(var(--v-theme-primary));
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}

.doc-reader__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  background: var(--reader-bg);
}

/* ── Miniatur-Leiste ─────────────────────────────────────────────────────── */
.doc-reader__rail {
  flex: 0 0 auto;
  width: 168px;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 8px 18px;
  border-right: 1px solid var(--reader-divider);
  background: var(--reader-panel-bg);
  contain: layout paint style;
  will-change: width, opacity, transform;
  transition:
    width 150ms cubic-bezier(0.2, 0, 0, 1),
    padding 150ms cubic-bezier(0.2, 0, 0, 1),
    border-color 150ms ease,
    opacity 110ms ease,
    transform 150ms cubic-bezier(0.2, 0, 0, 1);
}

.doc-reader__rail--hidden {
  width: 0;
  padding-left: 0;
  padding-right: 0;
  border-right-color: transparent;
  opacity: 0;
  pointer-events: none;
  transform: translateX(-6px);
}

.doc-reader__thumb {
  position: relative;
  display: block;
  padding: 4px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  line-height: 0;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
}
.doc-reader__thumb:hover {
  background: rgb(var(--reader-overlay-rgb) / 0.05);
  border-color: rgb(var(--reader-overlay-rgb) / 0.08);
}
.doc-reader__thumb--active {
  background: rgb(var(--v-theme-primary) / 0.12);
  border-color: rgb(var(--v-theme-primary) / 0.72);
}
.doc-reader__thumb--active:hover {
  background: rgb(var(--v-theme-primary) / 0.14);
  border-color: rgb(var(--v-theme-primary) / 0.72);
}
.doc-reader__thumb-canvas {
  display: block;
  width: 128px;
  min-height: 168px;
  border-radius: 4px;
  background: #fff;
  box-shadow: 0 4px 12px var(--reader-thumb-shadow);
  opacity: 0;
  transition: opacity 220ms ease;
}
.doc-reader__thumb-num {
  position: absolute;
  bottom: 8px;
  right: 8px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--reader-thumb-num-bg);
  color: #fff;
  font-size: 0.7rem;
  line-height: 18px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

/* ── Hauptansicht ─────────────────────────────────────────────────────────── */
.doc-reader__main {
  flex: 1 1 auto;
  min-width: 0;
  position: relative;
  contain: layout paint style;
  background:
    linear-gradient(90deg, var(--reader-bg) 0, var(--reader-panel-bg) 16%, var(--reader-panel-bg) 84%, var(--reader-bg) 100%);
}

.doc-reader__main :deep(.pdf-preview) {
  background: transparent;
}

.doc-reader__main :deep(.pdf-preview__viewer) {
  background: transparent;
}

.doc-reader__main :deep(.pdf-preview__toolbar) {
  top: 12px;
  left: 50%;
  right: auto;
  transform: translateX(-50%);
  width: auto;
  min-width: 0;
  min-height: 34px;
  justify-content: center;
  gap: var(--pdf-toolbar-group-gap);
  padding: 4px 8px;
  border: 1px solid var(--pdf-toolbar-border);
  border-radius: 999px;
  background: var(--pdf-toolbar-bg);
  box-shadow: var(--pdf-toolbar-shadow);
}

.doc-reader__main :deep(.pdf-preview__left-controls),
.doc-reader__main :deep(.pdf-preview__zoom-controls) {
  position: static;
}

.doc-reader__main :deep(.pdf-preview__pages) {
  padding: 0 24px 32px;
  gap: 22px;
}

.doc-reader__main :deep(.pdf-preview__page) {
  border-radius: 4px;
}

.doc-reader__main :deep(.pdf-preview__page:has(.pdf-preview__page-inner:not(:empty))) {
  box-shadow: 0 14px 34px var(--reader-page-shadow);
}

/* ── Werkzeug-Leiste ─────────────────────────────────────────────────────── */
.doc-reader__tools {
  flex: 0 0 auto;
  width: 56px;
  padding: 14px 8px;
  overflow: hidden;
  border-left: 1px solid var(--reader-divider);
  background: var(--reader-panel-bg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  contain: layout paint style;
  will-change: width, opacity, transform;
  transition:
    width 140ms cubic-bezier(0.2, 0, 0, 1),
    padding 140ms cubic-bezier(0.2, 0, 0, 1),
    border-color 140ms ease,
    opacity 110ms ease,
    transform 140ms cubic-bezier(0.2, 0, 0, 1);
}

.doc-reader__tools--hidden {
  width: 0;
  padding-left: 0;
  padding-right: 0;
  border-left-color: transparent;
  opacity: 0;
  pointer-events: none;
  transform: translateX(6px);
}

.doc-reader__tool-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: rgb(var(--reader-muted-rgb) / 0.78);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease, border-color 120ms ease, transform 120ms ease;
}

.doc-reader__tool-btn:hover {
  background: rgb(var(--reader-overlay-rgb) / 0.07);
  color: var(--reader-text);
}

.doc-reader__tool-btn:active {
  transform: scale(0.94);
}

.doc-reader__tool-btn--active {
  border-color: rgb(var(--v-theme-primary) / 0.46);
  background: rgb(var(--v-theme-primary) / 0.16);
  color: rgb(var(--v-theme-primary));
  box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary) / 0.22);
}

.doc-reader__tool-divider {
  width: 26px;
  height: 1px;
  margin: 2px 0;
  background: var(--reader-divider);
}

.doc-reader__color-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  /* Sichtbarer Rand auch für dunkle Farben (z. B. Schwarz) auf dem Panel. */
  border: 2px solid rgb(var(--reader-overlay-rgb) / 0.22);
  background: var(--swatch-color);
  cursor: pointer;
  padding: 0;
  transition: transform 120ms ease, border-color 120ms ease;
}

.doc-reader__color-btn:hover {
  transform: scale(1.1);
}

.doc-reader__color-btn--active {
  border-color: var(--reader-text);
  box-shadow: 0 0 0 2px var(--reader-panel-bg), 0 0 0 3px rgb(var(--v-theme-primary) / 0.5);
}

/* ── Notizen-Leiste ───────────────────────────────────────────────────────── */
.doc-reader__notes {
  flex: 0 0 auto;
  width: 310px;
  overflow-y: auto;
  overflow-x: hidden;
  border-left: 1px solid var(--reader-divider);
  background: var(--reader-panel-bg);
  display: flex;
  flex-direction: column;
  contain: layout paint style;
  will-change: width, opacity, transform;
  transition:
    width 150ms cubic-bezier(0.2, 0, 0, 1),
    border-color 150ms ease,
    opacity 110ms ease,
    transform 150ms cubic-bezier(0.2, 0, 0, 1);
}
.doc-reader__notes--hidden {
  width: 0;
  border-left-color: transparent;
  opacity: 0;
  pointer-events: none;
  transform: translateX(6px);
}
.doc-reader__notes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 18px 18px 12px;
  font-size: 0.9rem;
  font-weight: 650;
  color: var(--reader-text);
}
.doc-reader__notes-count {
  min-width: 24px;
  height: 22px;
  padding: 0 8px;
  border-radius: 11px;
  background: rgb(var(--reader-overlay-rgb) / 0.07);
  color: var(--reader-muted);
  font-size: 0.72rem;
  line-height: 22px;
  text-align: center;
}
.doc-reader__notes-empty {
  margin: 4px 18px;
  padding: 14px 12px;
  border: 1px dashed rgb(var(--reader-overlay-rgb) / 0.14);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--reader-muted);
  line-height: 1.5;
}

.doc-reader__notes-empty strong {
  color: rgb(var(--reader-text-rgb) / 0.86);
  font-size: 0.82rem;
  font-weight: 600;
}

.doc-reader__notes-empty span {
  font-size: 0.76rem;
}
.doc-reader__notes-list {
  list-style: none;
  margin: 0;
  padding: 4px 12px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Notizen: ein-/ausblenden + sanftes Nachrücken beim Umsortieren/Löschen. */
.note-enter-active,
.note-leave-active {
  transition: opacity 220ms ease, transform 220ms ease;
}
.note-enter-from,
.note-leave-to {
  opacity: 0;
  transform: translateX(14px);
}
.note-leave-active {
  position: absolute;
  left: 10px;
  right: 10px;
}
.note-move {
  transition: transform 240ms ease;
}
.doc-reader__note {
  position: relative;
  padding: 10px 38px 10px 12px;
  border: 1px solid rgb(var(--reader-overlay-rgb) / 0.08);
  border-left: 3px solid var(--note-color);
  border-radius: 8px;
  background: rgb(var(--reader-overlay-rgb) / 0.035);
  transition: background 120ms ease, border-color 120ms ease;
}
.doc-reader__note:hover {
  background: rgb(var(--reader-overlay-rgb) / 0.06);
  border-color: rgb(var(--reader-overlay-rgb) / 0.14);
}
.doc-reader__note-jump {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.doc-reader__note-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.doc-reader__note-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--note-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--note-color) 24%, transparent);
}
.doc-reader__note-quote {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.82rem;
  color: rgb(var(--reader-text-rgb) / 0.92);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.doc-reader__note-page {
  flex: 0 0 auto;
  padding: 2px 7px;
  border: 1px solid rgb(var(--reader-overlay-rgb) / 0.08);
  border-radius: 999px;
  background: rgb(var(--reader-overlay-rgb) / 0.04);
  font-size: 0.7rem;
  color: var(--reader-muted);
  font-variant-numeric: tabular-nums;
}
.doc-reader__note-link {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  margin-top: 6px;
  padding: 5px 8px;
  border: 1px solid rgb(24 95 165 / 0.3);
  border-radius: 7px;
  background: rgb(24 95 165 / 0.08);
  color: rgb(24 95 165 / 0.95);
  cursor: pointer;
  transition: background 120ms ease;
}
.doc-reader__note-link:hover {
  background: rgb(24 95 165 / 0.16);
}
.doc-reader__note-link-title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-reader__note-link-go {
  flex: 0 0 auto;
  opacity: 0.7;
}
.doc-reader__note-comment {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 0;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 0.78rem;
  color: rgb(var(--reader-muted-rgb) / 0.85);
  line-height: 1.4;
  cursor: text;
}
.doc-reader__note-comment--empty {
  color: rgb(var(--reader-muted-rgb) / 0.55);
  font-style: italic;
}
.doc-reader__note-input {
  width: 100%;
  margin-top: 6px;
  padding: 6px 8px;
  border: 1px solid rgb(var(--reader-overlay-rgb) / 0.18);
  border-radius: 6px;
  background: var(--reader-input-bg);
  color: var(--reader-text);
  font: inherit;
  font-size: 0.8rem;
  resize: vertical;
}
.doc-reader__note-edit-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.doc-reader__note-btn {
  padding: 3px 10px;
  border: 1px solid rgb(var(--v-theme-primary) / 0.5);
  border-radius: 6px;
  background: rgb(var(--v-theme-primary) / 0.12);
  color: rgb(var(--v-theme-primary));
  font-size: 0.75rem;
  cursor: pointer;
}
.doc-reader__note-btn--ghost {
  border-color: rgb(var(--v-theme-on-surface) / 0.16);
  background: transparent;
  color: rgb(var(--v-theme-on-surface) / 0.6);
}
.doc-reader__note-delete {
  position: absolute;
  top: 7px;
  right: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: rgb(var(--reader-muted-rgb) / 0.55);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}
.doc-reader__note:hover .doc-reader__note-delete,
.doc-reader__note-delete:focus-visible {
  opacity: 1;
}
.doc-reader__note-delete:hover {
  background: rgb(var(--v-theme-error) / 0.12);
  color: rgb(var(--v-theme-error));
}
</style>

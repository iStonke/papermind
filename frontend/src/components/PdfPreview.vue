<template>
  <div ref="rootEl" class="pdf-preview" role="region" aria-label="PDF Vorschau">

    <!-- Fehlerzustand -->
    <div v-if="errorMessage" class="pdf-preview__state pdf-preview__state--error">
      <v-icon size="20">mdi-file-alert-outline</v-icon>
      <div class="pdf-preview__state-title">Vorschau nicht verfügbar</div>
      <div class="pdf-preview__state-subtitle">{{ errorMessage }}</div>
    </div>

    <!-- Erstes Laden: Fortschrittsbalken -->
    <div v-else-if="isLoading" class="pdf-preview__state pdf-preview__state--loading">
      <div class="pdf-preview__progress-wrap" role="progressbar" :aria-valuenow="loadIndeterminate ? undefined : loadProgress" aria-valuemin="0" aria-valuemax="100">
        <div
          class="pdf-preview__progress-bar"
          :class="{ 'pdf-preview__progress-bar--indeterminate': loadIndeterminate }"
          :style="loadIndeterminate ? {} : { width: `${loadProgress}%` }"
        />
      </div>
      <span>Vorschau wird geladen…</span>
    </div>

    <template v-else>
      <!-- Toolbar: Seite + Zoom -->
      <div class="pdf-preview__toolbar" aria-label="PDF-Steuerung">
        <span class="pdf-preview__page-info" aria-live="polite">
          {{ currentPage }} / {{ pageInfos.length }}
        </span>
        <div class="pdf-preview__zoom-controls" role="group" aria-label="Zoom">
          <button
            class="pdf-preview__zoom-btn"
            :disabled="zoomIndex <= 0"
            aria-label="Verkleinern"
            @click="zoomOut"
          >−</button>
          <span class="pdf-preview__zoom-label">{{ zoomPercent }}%</span>
          <button
            class="pdf-preview__zoom-btn"
            :disabled="zoomIndex >= ZOOM_STEPS.length - 1"
            aria-label="Vergrößern"
            @click="zoomIn"
          >+</button>
        </div>
      </div>

      <!-- Seiten-Container (scrollbar) -->
      <div ref="pagesEl" class="pdf-preview__pages">
        <article
          v-for="info in pageInfos"
          :key="info.page"
          class="pdf-preview__page"
          :data-page="info.page"
          :style="pageStyle(info)"
        >
          <div
            :ref="el => setInnerRef(el, info.page)"
            class="pdf-preview__page-inner"
          />
        </article>
      </div>
    </template>

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import { TextLayer } from 'pdfjs-dist';
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';

GlobalWorkerOptions.workerSrc = pdfWorkerSrc;

// ─── Props & Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  src:           { type: String, default: '' },
  targetPage:    { type: Number, default: null },
  /** Text der im TextLayer hervorgehoben werden soll (z.B. citation.snippet) */
  highlightText: { type: String, default: '' },
});
const emit = defineEmits(['loaded', 'failed']);

// ─── Zoom ─────────────────────────────────────────────────────────────────────

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
const MAX_CACHED_PAGES = 12;

const zoomIndex = ref(2); // Standard: 1.0 = 100 %
const currentZoom = computed(() => ZOOM_STEPS[zoomIndex.value]);
const zoomPercent = computed(() => Math.round(currentZoom.value * 100));

function zoomIn() {
  if (zoomIndex.value < ZOOM_STEPS.length - 1) zoomIndex.value++;
}
function zoomOut() {
  if (zoomIndex.value > 0) zoomIndex.value--;
}

// ─── State ────────────────────────────────────────────────────────────────────

const rootEl     = ref(null);
const pagesEl    = ref(null);
const isLoading  = ref(false);
const errorMessage = ref('');

/** Ladefortschritt (0-100); -1 = unbekannte Größe */
const loadProgress    = ref(0);
const loadIndeterminate = ref(false);

/** Dimensionen aller Seiten – ohne Rendering befüllt */
const pageInfos = ref([]); // [{ page, width, height }]

/** Bereits gerenderte Seiten (plain Set – DOM wird imperativ verwaltet) */
const renderedPages = new Set();

/** Aktuell sichtbare Seite (für Seitenanzeige) */
const currentPage = ref(1);

// ─── Interne Handles ──────────────────────────────────────────────────────────

let loadEpoch      = 0;
let pdfDoc         = null;
let activeLoadTask = null;
let renderObserver = null;
let resizeObserver = null;
let scrollRafId    = null;
const renderQueue  = new Set();

/** Imperative Refs: pageNum → inneres HTMLElement */
const pageInnerRefs = new Map();

function setInnerRef(el, pageNum) {
  if (el) pageInnerRefs.set(pageNum, el);
  else    pageInnerRefs.delete(pageNum);
}

// ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

function containerWidth() {
  return Math.max(340, (pagesEl.value?.clientWidth || 900));
}

function computeScale(info) {
  const maxW = Math.min(containerWidth() - 28, 980);
  const base = maxW / info.width;
  return Math.max(0.2, base * currentZoom.value);
}

function pageStyle(info) {
  const scale = computeScale(info);
  return {
    width:  `${Math.floor(info.width  * scale)}px`,
    height: `${Math.floor(info.height * scale)}px`,
  };
}

// ─── Highlighting ─────────────────────────────────────────────────────────────

/**
 * Extrahiert Suchbegriffe aus dem highlightText-Prop:
 * Split nach Whitespace, entfernt Sonderzeichen, filtert kurze Wörter.
 */
function extractTerms() {
  if (!props.highlightText) return [];
  return props.highlightText
    .split(/\s+/)
    .map(w => w.replace(/[^\wäöüÄÖÜß]/gi, ''))
    .filter(w => w.length >= 3);
}

/**
 * Markiert passende Spans im TextLayer mit der Klasse `pm-highlight`.
 * Wird nach jedem TextLayer-Rendering aufgerufen.
 */
function applyHighlights(textLayerDiv) {
  const terms = extractTerms();
  if (!terms.length) return;

  const spans = textLayerDiv.querySelectorAll('span');
  for (const span of spans) {
    const text = span.textContent || '';
    if (terms.some(term => text.toLowerCase().includes(term.toLowerCase()))) {
      span.classList.add('pm-highlight');
    }
  }
}

/**
 * Wird aufgerufen wenn sich highlightText ändert ohne neues PDF-Loading.
 * Entfernt alte Markierungen und setzt neue auf bereits gerenderten Seiten.
 */
watch(() => props.highlightText, () => {
  for (const [pageNum, el] of pageInnerRefs.entries()) {
    // Alte Markierungen entfernen
    el.querySelectorAll('.pm-highlight').forEach(s => s.classList.remove('pm-highlight'));
    // Neue setzen wenn Seite bereits gerendert
    if (renderedPages.has(pageNum)) {
      const tl = el.querySelector('.textLayer');
      if (tl) applyHighlights(tl);
    }
  }
});

// ─── Rendering ───────────────────────────────────────────────────────────────

async function renderPage(pageNum) {
  if (renderQueue.has(pageNum)) return;
  if (renderedPages.has(pageNum)) return;
  if (!pdfDoc) return;

  const epoch = loadEpoch;
  renderQueue.add(pageNum);

  try {
    const page = await pdfDoc.getPage(pageNum);
    if (epoch !== loadEpoch) return;

    const info = pageInfos.value[pageNum - 1];
    if (!info) return;

    const innerEl = pageInnerRefs.get(pageNum);
    if (!innerEl) return;

    const scale    = computeScale(info);
    const viewport = page.getViewport({ scale });

    // Canvas erstellen und rendern
    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    canvas.width  = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);

    await page.render({ canvasContext: ctx, viewport, background: 'rgb(255,255,255)' }).promise;
    if (epoch !== loadEpoch) return;

    // Text-Layer erstellen
    const textLayerDiv = document.createElement('div');
    textLayerDiv.className = 'textLayer';

    const textLayer = new TextLayer({
      textContentSource: page.streamTextContent(),
      container: textLayerDiv,
      viewport,
    });
    await textLayer.render();
    if (epoch !== loadEpoch) return;

    // Highlights anwenden
    applyHighlights(textLayerDiv);

    // LRU-Eviction: älteste Seite entfernen wenn Cache voll
    if (renderedPages.size >= MAX_CACHED_PAGES) {
      const oldest = renderedPages.values().next().value;
      renderedPages.delete(oldest);
      const oldEl = pageInnerRefs.get(oldest);
      if (oldEl) oldEl.innerHTML = '';
    }

    // --total-scale-factor für TextLayer-Positionierung
    innerEl.style.setProperty('--total-scale-factor', String(scale));

    // Canvas + TextLayer in DOM einhängen
    innerEl.innerHTML = '';
    innerEl.appendChild(canvas);
    innerEl.appendChild(textLayerDiv);

    renderedPages.add(pageNum);
    page.cleanup();
  } catch (_err) {
    // Einzelseite konnte nicht gerendert werden – kein Fatal-Error
  } finally {
    renderQueue.delete(pageNum);
  }
}

// ─── Observer Setup ──────────────────────────────────────────────────────────

function recalcCurrentPage() {
  const container = pagesEl.value;
  if (!container) return;
  const mid = container.scrollTop + container.clientHeight * 0.5;
  const articles = container.querySelectorAll('.pdf-preview__page');
  let best = 1, bestDist = Infinity;
  for (const el of articles) {
    const dist = Math.abs(el.offsetTop + el.offsetHeight * 0.5 - mid);
    if (dist < bestDist) { bestDist = dist; best = Number(el.dataset.page); }
  }
  currentPage.value = best;
}

function onScroll() {
  if (scrollRafId) return;
  scrollRafId = requestAnimationFrame(() => { scrollRafId = null; recalcCurrentPage(); });
}

function teardownObservers() {
  renderObserver?.disconnect();
  renderObserver = null;
  pagesEl.value?.removeEventListener('scroll', onScroll);
}

async function setupObservers() {
  teardownObservers();
  await nextTick();

  const container = pagesEl.value;
  if (!container) return;

  renderObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) renderPage(Number(entry.target.dataset.page));
      }
    },
    { root: container, rootMargin: '600px 0px', threshold: 0 }
  );

  container.querySelectorAll('.pdf-preview__page').forEach(el => renderObserver.observe(el));
  container.addEventListener('scroll', onScroll, { passive: true });
  recalcCurrentPage();
}

// ─── Zoom-Reaktion ───────────────────────────────────────────────────────────

watch(currentZoom, async () => {
  if (!pdfDoc) return;
  renderedPages.clear();
  renderQueue.clear();
  for (const el of pageInnerRefs.values()) el.innerHTML = '';
  await setupObservers();
});

// ─── PDF Laden ───────────────────────────────────────────────────────────────

async function loadPdf(src) {
  const epoch = ++loadEpoch;

  teardownObservers();
  renderedPages.clear();
  renderQueue.clear();
  pageInnerRefs.clear();
  pageInfos.value  = [];
  currentPage.value = 1;
  errorMessage.value = '';
  loadProgress.value = 0;
  loadIndeterminate.value = false;

  if (activeLoadTask) { try { activeLoadTask.destroy(); } catch (_) {} activeLoadTask = null; }
  if (pdfDoc)         { try { pdfDoc.destroy(); }         catch (_) {} pdfDoc = null; }

  if (!src) return;

  isLoading.value = true;

  try {
    activeLoadTask = getDocument({ url: src, withCredentials: false });

    // Ladefortschritt
    activeLoadTask.onProgress = ({ loaded, total }) => {
      if (epoch !== loadEpoch) return;
      if (total > 0) {
        loadIndeterminate.value = false;
        loadProgress.value = Math.round((loaded / total) * 100);
      } else {
        loadIndeterminate.value = true;
      }
    };

    const doc = await activeLoadTask.promise;
    if (epoch !== loadEpoch) return;

    pdfDoc = doc;
    loadProgress.value = 100;

    // Dimensionen aller Seiten vorab lesen
    const infos = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const vp   = page.getViewport({ scale: 1 });
      infos.push({ page: i, width: vp.width, height: vp.height });
      page.cleanup();
    }
    if (epoch !== loadEpoch) return;

    pageInfos.value = infos;
    isLoading.value = false;

    await setupObservers();
    emit('loaded');

    await nextTick();
    scrollToPage(props.targetPage);

  } catch (err) {
    if (epoch !== loadEpoch) return;
    console.warn('PdfPreview load failed', err);
    isLoading.value = false;
    errorMessage.value = 'Vorschau konnte nicht geladen werden.';
    emit('failed', err);
  }
}

// ─── Seitennavigation ────────────────────────────────────────────────────────

function scrollToPage(pageNum) {
  if (!pageNum || pageNum < 1 || !pagesEl.value) return;
  const el = pagesEl.value.querySelector(`.pdf-preview__page[data-page="${pageNum}"]`);
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ─── Watchers ────────────────────────────────────────────────────────────────

watch(() => props.src,        (src)  => loadPdf(src), { immediate: true });
watch(() => props.targetPage, (page) => nextTick(() => scrollToPage(page)));

// ─── Resize ──────────────────────────────────────────────────────────────────

function onResize() {
  if (!pdfDoc) return;
  renderedPages.clear();
  renderQueue.clear();
  for (const el of pageInnerRefs.values()) el.innerHTML = '';
  setupObservers();
}

watch(pagesEl, (el) => {
  resizeObserver?.disconnect();
  if (!el) return;
  resizeObserver = new ResizeObserver(onResize);
  resizeObserver.observe(el);
});

// ─── Cleanup ─────────────────────────────────────────────────────────────────

onBeforeUnmount(() => {
  loadEpoch++;
  teardownObservers();
  resizeObserver?.disconnect();
  if (scrollRafId)    cancelAnimationFrame(scrollRafId);
  if (activeLoadTask) try { activeLoadTask.destroy(); } catch (_) {}
  if (pdfDoc)         try { pdfDoc.destroy(); }         catch (_) {}
});
</script>

<style scoped>
.pdf-preview {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-pdf-stage-bg, rgb(var(--v-theme-surface)));
}

/* ── Toolbar ─────────────────────────────────────────────────────────────── */
.pdf-preview__toolbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface) / 0.08);
  gap: 12px;
  min-height: 38px;
}

.pdf-preview__page-info {
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface) / 0.55);
  white-space: nowrap;
  min-width: 3rem;
}

.pdf-preview__zoom-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pdf-preview__zoom-btn {
  width: 26px;
  height: 26px;
  border: 1px solid rgb(var(--v-theme-on-surface) / 0.18);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  color: rgb(var(--v-theme-on-surface));
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 120ms ease, opacity 120ms ease;
  user-select: none;
}

.pdf-preview__zoom-btn:hover:not(:disabled) {
  background: rgb(var(--v-theme-on-surface) / 0.08);
}

.pdf-preview__zoom-btn:disabled {
  opacity: 0.3;
  cursor: default;
}

.pdf-preview__zoom-label {
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface) / 0.7);
  min-width: 2.8rem;
  text-align: center;
}

/* ── Seiten-Scrollcontainer ─────────────────────────────────────────────── */
.pdf-preview__pages {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 14px;
}

/* ── Einzelne Seite ─────────────────────────────────────────────────────── */
.pdf-preview__page {
  flex: 0 0 auto;
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.14);
}

.pdf-preview__page-inner {
  position: absolute;
  inset: 0;
}

/* Shimmer solange noch nicht gerendert */
.pdf-preview__page-inner:empty {
  background: rgb(var(--v-theme-on-surface) / 0.05);
  animation: pdf-shimmer 1.4s ease-in-out infinite;
}

@keyframes pdf-shimmer {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}

.pdf-preview__page-inner :deep(canvas) {
  width: 100%;
  height: 100%;
  display: block;
}

/* TextLayer */
.pdf-preview__page-inner :deep(.textLayer) {
  position: absolute;
  inset: 0;
  overflow: hidden;
  line-height: 1;
  opacity: 1;
}

.pdf-preview__page-inner :deep(.textLayer span),
.pdf-preview__page-inner :deep(.textLayer br) {
  color: transparent;
  cursor: text;
}

.pdf-preview__page-inner :deep(.textLayer ::selection) {
  background: rgba(0, 120, 255, 0.25);
  color: transparent;
}

/* Suchmarkierung */
.pdf-preview__page-inner :deep(.textLayer .pm-highlight) {
  background: rgba(255, 200, 0, 0.45);
  border-radius: 2px;
  color: transparent;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}

/* ── Ladefortschritt ────────────────────────────────────────────────────── */
.pdf-preview__state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 12px;
  font-size: 0.86rem;
  opacity: 0.78;
  padding: 24px;
}

.pdf-preview__state--loading {
  gap: 10px;
}

.pdf-preview__progress-wrap {
  width: 160px;
  height: 3px;
  background: rgb(var(--v-theme-on-surface) / 0.12);
  border-radius: 2px;
  overflow: hidden;
}

.pdf-preview__progress-bar {
  height: 100%;
  background: rgb(var(--v-theme-primary));
  border-radius: 2px;
  transition: width 120ms ease;
  will-change: width, transform;
}

.pdf-preview__progress-bar--indeterminate {
  width: 40% !important;
  transition: none;
  animation: pdf-progress-slide 1.2s ease-in-out infinite;
}

@keyframes pdf-progress-slide {
  0%   { transform: translateX(-250%); }
  100% { transform: translateX(450%); }
}

.pdf-preview__state--error {
  gap: 8px;
}

.pdf-preview__state-title {
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.2;
}

.pdf-preview__state-subtitle {
  font-size: 0.82rem;
  opacity: 0.78;
  line-height: 1.35;
}
</style>

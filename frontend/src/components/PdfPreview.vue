<template>
  <div ref="rootEl" class="pdf-preview" role="region" aria-label="PDF Vorschau">

    <!-- Fehlerzustand -->
    <div v-if="errorMessage" class="pdf-preview__state pdf-preview__state--error">
      <v-icon size="20">mdi-file-alert-outline</v-icon>
      <div class="pdf-preview__state-title">Vorschau nicht verfügbar</div>
      <div class="pdf-preview__state-subtitle">{{ errorMessage }}</div>
    </div>

    <!-- Erstes Laden -->
    <div v-else-if="isLoading" class="pdf-preview__state pdf-preview__state--loading">
      <v-progress-circular size="18" width="2" indeterminate />
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
          <img
            v-if="renderedPages.has(info.page)"
            :src="renderedPages.get(info.page)"
            :alt="`Seite ${info.page}`"
            draggable="false"
            class="pdf-preview__page-img"
          />
          <div v-else class="pdf-preview__placeholder" :style="{ width: '100%', height: '100%' }" />
        </article>
      </div>
    </template>

  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = pdfWorkerSrc;

// ─── Props & Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  src: { type: String, default: '' },
  targetPage: { type: Number, default: null }
});
const emit = defineEmits(['loaded', 'failed']);

// ─── Zoom ─────────────────────────────────────────────────────────────────────

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
const MAX_CACHED_PAGES = 12;

const zoomIndex = ref(2); // Standard: 1.0 = 100 %
const currentZoom = computed(() => ZOOM_STEPS[zoomIndex.value]);
const zoomPercent = computed(() => Math.round(currentZoom.value * 100));

function zoomIn() {
  if (zoomIndex.value < ZOOM_STEPS.length - 1) {
    zoomIndex.value++;
  }
}
function zoomOut() {
  if (zoomIndex.value > 0) {
    zoomIndex.value--;
  }
}

// ─── State ────────────────────────────────────────────────────────────────────

const rootEl = ref(null);
const pagesEl = ref(null);
const isLoading = ref(false);
const errorMessage = ref('');

/** Dimensionen aller Seiten – ohne Rendering befüllt */
const pageInfos = ref([]); // [{ page, width, height }]

/** Bereits gerenderte Seiten: pageNum → dataUrl */
const renderedPages = reactive(new Map());

/** Aktuell sichtbare Seite (für Seitenanzeige) */
const currentPage = ref(1);

// ─── Interne Handles ──────────────────────────────────────────────────────────

let loadEpoch = 0;
let pdfDoc = null;
let activeLoadTask = null;
let renderObserver = null;
let visibilityObserver = null;
let resizeObserver = null;
const renderQueue = new Set();

// ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

function containerWidth() {
  return Math.max(340, (pagesEl.value?.clientWidth || 900));
}

function computeScale(info) {
  const maxW = Math.min(containerWidth() - 28, 980);
  const base = maxW / info.width;
  return Math.max(0.2, base * currentZoom.value);
}

/** Inline-Style für jedes Seiten-article (bestimmt Scrollhöhe vor dem Rendern) */
function pageStyle(info) {
  const scale = computeScale(info);
  const w = Math.floor(info.width * scale);
  const h = Math.floor(info.height * scale);
  return { width: `${w}px`, height: `${h}px` };
}

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

    const scale = computeScale(info);
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);

    await page.render({ canvasContext: ctx, viewport, background: 'rgb(255,255,255)' }).promise;
    if (epoch !== loadEpoch) return;

    // LRU-Eviction: älteste Seite entfernen wenn Cache voll
    if (renderedPages.size >= MAX_CACHED_PAGES) {
      const oldest = renderedPages.keys().next().value;
      renderedPages.delete(oldest);
    }

    renderedPages.set(pageNum, canvas.toDataURL('image/webp', 0.92));
    page.cleanup();
  } catch (_err) {
    // Einzelseite konnte nicht gerendert werden – kein Fatal-Error
  } finally {
    renderQueue.delete(pageNum);
  }
}

// ─── Observer Setup ──────────────────────────────────────────────────────────

function teardownObservers() {
  renderObserver?.disconnect();
  visibilityObserver?.disconnect();
  renderObserver = null;
  visibilityObserver = null;
}

async function setupObservers() {
  teardownObservers();
  await nextTick();

  const container = pagesEl.value;
  if (!container) return;

  // Render-Observer: Seiten 600 px vor Eintritt in den Viewport rendern
  renderObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          renderPage(Number(entry.target.dataset.page));
        }
      }
    },
    { root: container, rootMargin: '600px 0px', threshold: 0 }
  );

  // Sichtbarkeits-Observer: welche Seite ist gerade am stärksten sichtbar?
  visibilityObserver = new IntersectionObserver(
    (entries) => {
      let bestRatio = 0;
      let bestPage = currentPage.value;
      for (const entry of entries) {
        if (entry.isIntersecting && entry.intersectionRatio > bestRatio) {
          bestRatio = entry.intersectionRatio;
          bestPage = Number(entry.target.dataset.page);
        }
      }
      if (bestRatio > 0) currentPage.value = bestPage;
    },
    { root: container, threshold: [0, 0.25, 0.5, 0.75, 1.0] }
  );

  const articles = container.querySelectorAll('.pdf-preview__page');
  articles.forEach((el) => {
    renderObserver.observe(el);
    visibilityObserver.observe(el);
  });
}

// ─── Zoom-Reaktion ───────────────────────────────────────────────────────────

watch(currentZoom, async () => {
  if (!pdfDoc) return;
  // Alle gecachten Seiten verwerfen (falscher Maßstab) und neu rendern
  renderedPages.clear();
  renderQueue.clear();
  await setupObservers();
});

// ─── PDF Laden ───────────────────────────────────────────────────────────────

async function loadPdf(src) {
  const epoch = ++loadEpoch;

  // Aufräumen
  teardownObservers();
  renderedPages.clear();
  renderQueue.clear();
  pageInfos.value = [];
  currentPage.value = 1;
  errorMessage.value = '';

  if (activeLoadTask) {
    try { activeLoadTask.destroy(); } catch (_) {}
    activeLoadTask = null;
  }
  if (pdfDoc) {
    try { pdfDoc.destroy(); } catch (_) {}
    pdfDoc = null;
  }

  if (!src) return;

  isLoading.value = true;

  try {
    activeLoadTask = getDocument({ url: src, withCredentials: false });
    const doc = await activeLoadTask.promise;

    if (epoch !== loadEpoch) return;

    pdfDoc = doc;

    // Dimensionen aller Seiten vorab lesen (kein Rendering, sehr schnell)
    const infos = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const vp = page.getViewport({ scale: 1 });
      infos.push({ page: i, width: vp.width, height: vp.height });
      page.cleanup();
    }

    if (epoch !== loadEpoch) return;

    pageInfos.value = infos;
    isLoading.value = false;

    await setupObservers();
    emit('loaded');

    // Zur Zielseite springen (nach nächstem Tick damit DOM steht)
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

watch(() => props.src, (src) => loadPdf(src), { immediate: true });

watch(() => props.targetPage, (page) => {
  nextTick(() => scrollToPage(page));
});

// ─── Resize: bei Größenänderung Seiten neu rendern ───────────────────────────

function onResize() {
  if (!pdfDoc) return;
  renderedPages.clear();
  renderQueue.clear();
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
  if (activeLoadTask) try { activeLoadTask.destroy(); } catch (_) {}
  if (pdfDoc) try { pdfDoc.destroy(); } catch (_) {}
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
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.14);
  /* Dimension wird per :style gesetzt */
}

.pdf-preview__page-img {
  width: 100%;
  height: 100%;
  display: block;
}

/* Platzhalter solange Seite noch nicht gerendert ist */
.pdf-preview__placeholder {
  background: rgb(var(--v-theme-on-surface) / 0.05);
  animation: pdf-shimmer 1.4s ease-in-out infinite;
}

@keyframes pdf-shimmer {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.6; }
}

/* ── Zustands-Screens ───────────────────────────────────────────────────── */
.pdf-preview__state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  font-size: 0.86rem;
  opacity: 0.78;
  padding: 24px;
}

.pdf-preview__state--loading {
  flex-direction: row;
  gap: 10px;
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

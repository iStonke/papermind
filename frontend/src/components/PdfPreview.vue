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

    <div
      v-else
      class="pdf-preview__viewer"
      :class="{ 'pdf-preview__viewer--ready': firstPageReady }"
    >
      <!-- Toolbar: Seite + Zoom + Treffer -->
      <div class="pdf-preview__toolbar" aria-label="PDF-Steuerung">
        <span class="pdf-preview__page-info" aria-live="polite">
          {{ currentPage }} / {{ pageInfos.length }}
        </span>

        <!-- Treffer-Navigation (nur wenn Suche aktiv) -->
        <div
          v-if="highlightText"
          class="pdf-preview__match-controls"
          aria-label="PDF-Treffer"
        >
          <button
            class="pdf-preview__match-nav-btn"
            :disabled="highlightCount === 0"
            aria-label="Vorheriger Treffer"
            @click="navigateHighlight(-1)"
          >‹</button>
          <span
            class="pdf-preview__match-badge"
            :class="{ 'pdf-preview__match-badge--zero': highlightCount === 0 }"
            aria-live="polite"
          >
            {{ highlightCount === 0 ? 'Kein Treffer' : `${highlightCount} Treffer` }}
          </span>
          <button
            class="pdf-preview__match-nav-btn"
            :disabled="highlightCount === 0"
            aria-label="Nächster Treffer"
            @click="navigateHighlight(1)"
          >›</button>
        </div>

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
    </div>

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
const PDF_BYTE_CACHE_MAX_ENTRIES = 4;
const PAGE_INFO_BATCH_SIZE = 6;

const pdfByteCache = new Map();

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

/** Erste Seite wurde gerendert → Viewer einblenden */
const firstPageReady = ref(false);

/** Dimensionen aller Seiten – ohne Rendering befüllt */
const pageInfos = ref([]); // [{ page, width, height }]

/** Bereits gerenderte Seiten (plain Set – DOM wird imperativ verwaltet) */
const renderedPages = new Set();

/** Aktuell sichtbare Seite (für Seitenanzeige) */
const currentPage = ref(1);

/** Gesamtanzahl Treffer über alle gerenderten Seiten */
const highlightCount = ref(0);
const activeHighlightIndex = ref(-1);

// ─── Interne Handles ──────────────────────────────────────────────────────────

let loadEpoch      = 0;
let pdfDoc         = null;
let activeLoadTask = null;
let renderObserver = null;
let resizeObserver = null;
let lastRenderWidth = 0;
let resizeRaf      = 0;
let scrollRafId    = null;
let highlightIdSeq = 0;
let highlightFlashTimer = 0;
const renderQueue  = new Set();
let highlightTargets = [];

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

function pdfCacheKey(src) {
  try {
    const url = new URL(src, window.location.origin);
    url.searchParams.delete('token');
    return url.toString();
  } catch {
    return String(src || '').replace(/([?&])token=[^&]*/g, '$1').replace(/[?&]$/, '');
  }
}

function rememberPdfBytes(cacheKey, bytes) {
  if (!cacheKey || !bytes?.byteLength) return;
  if (pdfByteCache.has(cacheKey)) pdfByteCache.delete(cacheKey);
  pdfByteCache.set(cacheKey, bytes);
  while (pdfByteCache.size > PDF_BYTE_CACHE_MAX_ENTRIES) {
    const oldestKey = pdfByteCache.keys().next().value;
    pdfByteCache.delete(oldestKey);
  }
}

async function fetchPdfBytes(src, epoch) {
  const cacheKey = pdfCacheKey(src);
  const cached = pdfByteCache.get(cacheKey);
  if (cached?.byteLength) {
    loadIndeterminate.value = false;
    loadProgress.value = 100;
    return cached;
  }

  const response = await fetch(src);
  if (!response.ok) {
    throw new Error(`PDF request failed (${response.status})`);
  }

  const total = Number(response.headers.get('content-length') || 0);
  if (!response.body) {
    loadIndeterminate.value = total <= 0;
    const bytes = await response.arrayBuffer();
    rememberPdfBytes(cacheKey, bytes);
    return bytes;
  }

  const reader = response.body.getReader();
  const chunks = [];
  let loaded = 0;
  loadIndeterminate.value = total <= 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (epoch !== loadEpoch) {
      try { reader.cancel(); } catch (_) {}
      throw new Error('PDF load cancelled');
    }
    chunks.push(value);
    loaded += value.byteLength;
    if (total > 0) {
      loadIndeterminate.value = false;
      loadProgress.value = Math.round((loaded / total) * 85);
    }
  }

  const bytes = new Uint8Array(loaded);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  rememberPdfBytes(cacheKey, bytes.buffer);
  return bytes.buffer;
}

async function readPageInfo(doc, pageNum) {
  const page = await doc.getPage(pageNum);
  const vp = page.getViewport({ scale: 1 });
  page.cleanup();
  return { page: pageNum, width: vp.width, height: vp.height };
}

async function hydrateRemainingPageInfos(doc, epoch) {
  const pageCount = doc.numPages;
  for (let start = 2; start <= pageCount; start += PAGE_INFO_BATCH_SIZE) {
    const end = Math.min(pageCount, start + PAGE_INFO_BATCH_SIZE - 1);
    const infos = await Promise.all(
      Array.from({ length: end - start + 1 }, (_, index) => readPageInfo(doc, start + index))
    );
    if (epoch !== loadEpoch) return;

    const nextInfos = pageInfos.value.slice();
    for (const info of infos) {
      nextInfos[info.page - 1] = info;
    }
    pageInfos.value = nextInfos;
    await nextTick();
  }
}

// ─── Highlighting ─────────────────────────────────────────────────────────────

function nextHighlightId() {
  highlightIdSeq += 1;
  return `pmh-${highlightIdSeq}`;
}

/**
 * Baut eine Liste von Suchbegriffen auf:
 * - Der gesamte highlightText als Phrase (falls >= 2 Zeichen)
 * - Plus einzelne Wörter >= 2 Zeichen (für Teilwort-Treffer)
 * Duplikate werden entfernt.
 */
function extractTerms() {
  const raw = (props.highlightText || '').trim();
  if (!raw) return [];

  const terms = new Set();
  // Ganzen Ausdruck als Phrase versuchen
  if (raw.length >= 2) terms.add(raw.toLowerCase());
  // Einzelwörter
  for (const w of raw.split(/\s+/)) {
    const clean = w.replace(/[^\wäöüÄÖÜß]/gi, '');
    if (clean.length >= 2) terms.add(clean.toLowerCase());
  }
  // Längste Terme zuerst (verhindert Überlappungen)
  return [...terms].sort((a, b) => b.length - a.length);
}

/**
 * Markiert Treffer im TextLayer.
 * Strategie:
 *   1. Alle Textknoten zu einem Flat-String zusammenführen und Treffer suchen.
 *   2. Liegt der Treffer innerhalb eines einzelnen Textknotens → <mark> via Range.
 *   3. Liegt er über mehrere Knoten (pdfjs teilt manchmal zeichenweise auf) →
 *      CSS-Klasse pm-highlight auf die betroffenen Eltern-Spans setzen.
 * Gibt die Anzahl der gefundenen Treffer zurück.
 */
function applyHighlights(textLayerDiv) {
  const terms = extractTerms();
  if (!terms.length) return 0;

  // Alle Textknoten in Dokumentenreihenfolge sammeln
  const walker = document.createTreeWalker(textLayerDiv, NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  let n;
  while ((n = walker.nextNode())) nodes.push(n);
  if (!nodes.length) return 0;

  // Flat-String + Offset-Karte
  const offsets = [];
  let pos = 0;
  for (const node of nodes) {
    offsets.push(pos);
    pos += node.textContent.length;
  }
  const fullText = nodes.map(nd => nd.textContent).join('').toLowerCase();

  // Treffer finden (keine Überlappungen)
  const matches = [];
  const covered = new Uint8Array(fullText.length);
  for (const term of terms) {
    let idx = 0;
    while (idx < fullText.length) {
      const found = fullText.indexOf(term, idx);
      if (found === -1) break;
      if (!covered.slice(found, found + term.length).some(Boolean)) {
        matches.push({ start: found, end: found + term.length });
        covered.fill(1, found, found + term.length);
      }
      idx = found + 1;
    }
  }
  if (!matches.length) return 0;

  // Rückwärts anwenden (DOM-Offsets bleiben stabil)
  matches.sort((a, b) => b.start - a.start);
  let count = 0;

  for (const { start, end } of matches) {
    const highlightId = nextHighlightId();
    // Startknoten ermitteln
    let si = nodes.length - 1;
    while (si > 0 && offsets[si] > start) si--;
    // Endknoten ermitteln
    let ei = nodes.length - 1;
    while (ei > 0 && offsets[ei] >= end) ei--;

    if (si === ei) {
      // ── Treffer liegt in einem einzigen Textknoten → <mark> via Range ──
      try {
        const range = document.createRange();
        range.setStart(nodes[si], start - offsets[si]);
        range.setEnd(nodes[si], end - offsets[si]);
        const mark = document.createElement('mark');
        mark.className = 'pm-highlight';
        mark.dataset.pmHighlightId = highlightId;
        range.surroundContents(mark);
        count++;
      } catch (_) {
        // Fallback: Eltern-Span markieren
        const p = nodes[si].parentElement;
        if (p && !p.classList.contains('pm-highlight')) {
          p.classList.add('pm-highlight');
          p.dataset.pmHighlightId = highlightId;
          count++;
        }
      }
    } else {
      // ── Treffer über mehrere Knoten → Eltern-Spans mit Klasse markieren ──
      let marked = false;
      for (let i = si; i <= ei; i++) {
        const p = nodes[i].parentElement;
        if (p && !p.classList.contains('pm-highlight')) {
          p.classList.add('pm-highlight');
          p.dataset.pmHighlightId = highlightId;
          marked = true;
        }
      }
      if (marked) count++;
    }
  }

  return count;
}

function rebuildHighlightTargets() {
  const root = pagesEl.value;
  const activeId = highlightTargets[activeHighlightIndex.value]?.id || '';
  if (!root) {
    highlightTargets = [];
    highlightCount.value = 0;
    activeHighlightIndex.value = -1;
    return;
  }

  const groups = new Map();
  root.querySelectorAll('.textLayer .pm-highlight[data-pm-highlight-id]').forEach((element) => {
    const id = element.dataset.pmHighlightId;
    if (!id) return;
    if (!groups.has(id)) {
      groups.set(id, {
        id,
        page: Number(element.closest('.pdf-preview__page')?.dataset.page || 0),
        elements: [],
      });
    }
    groups.get(id).elements.push(element);
  });

  highlightTargets = [...groups.values()];
  highlightCount.value = highlightTargets.length;

  if (!highlightTargets.length) {
    activeHighlightIndex.value = -1;
    applyActiveHighlightClasses();
    return;
  }

  const previousIndex = highlightTargets.findIndex((target) => target.id === activeId);
  activeHighlightIndex.value = previousIndex >= 0 ? previousIndex : Math.min(activeHighlightIndex.value, highlightTargets.length - 1);
  applyActiveHighlightClasses();
}

function applyActiveHighlightClasses() {
  const root = pagesEl.value;
  if (!root) return;
  root.querySelectorAll('.pm-highlight--active, .pm-highlight--flash').forEach((element) => {
    element.classList.remove('pm-highlight--active', 'pm-highlight--flash');
  });
  const target = highlightTargets[activeHighlightIndex.value];
  if (!target) return;
  target.elements.forEach((element) => element.classList.add('pm-highlight--active'));
}

function flashActiveHighlight() {
  const target = highlightTargets[activeHighlightIndex.value];
  if (!target) return;
  if (highlightFlashTimer) window.clearTimeout(highlightFlashTimer);
  target.elements.forEach((element) => element.classList.add('pm-highlight--flash'));
  highlightFlashTimer = window.setTimeout(() => {
    target.elements.forEach((element) => element.classList.remove('pm-highlight--flash'));
    highlightFlashTimer = 0;
  }, 650);
}

function navigateHighlight(delta) {
  if (!highlightTargets.length) return;
  const current = activeHighlightIndex.value >= 0 ? activeHighlightIndex.value : (delta < 0 ? 0 : -1);
  activeHighlightIndex.value = (current + delta + highlightTargets.length) % highlightTargets.length;
  applyActiveHighlightClasses();
  const target = highlightTargets[activeHighlightIndex.value];
  const element = target?.elements?.[0];
  if (target?.page) currentPage.value = target.page;
  element?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  flashActiveHighlight();
}

/** Entfernt alle Markierungen (mark-Elemente und pm-highlight-Klassen). */
function clearHighlights(el) {
  // <mark>-Elemente auflösen
  el.querySelectorAll('mark.pm-highlight').forEach(mark => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  });
  // CSS-Klassen entfernen (Cross-Span-Fallback)
  el.querySelectorAll('.pm-highlight').forEach((e) => {
    e.classList.remove('pm-highlight', 'pm-highlight--active', 'pm-highlight--flash');
    e.removeAttribute('data-pm-highlight-id');
  });
}

/**
 * Wird aufgerufen wenn sich highlightText ändert ohne neues PDF-Loading.
 * Entfernt alte <mark>-Elemente und markiert neu.
 */
watch(() => props.highlightText, () => {
  highlightIdSeq = 0;
  activeHighlightIndex.value = -1;
  for (const [pageNum, el] of pageInnerRefs.entries()) {
    clearHighlights(el);
    if (renderedPages.has(pageNum)) {
      const tl = el.querySelector('.textLayer');
      if (tl) applyHighlights(tl);
    }
  }
  rebuildHighlightTargets();
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
    // pdfjs kann Spans intern via setTimeout/rAF nachladen – einen Tick warten
    await new Promise(resolve => setTimeout(resolve, 0));
    if (epoch !== loadEpoch) return;

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

    // Highlights anwenden (nach DOM-Einhängen, damit normalize() korrekt arbeitet)
    applyHighlights(textLayerDiv);
    rebuildHighlightTargets();

    renderedPages.add(pageNum);
    if (!firstPageReady.value) firstPageReady.value = true;
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
  highlightTargets = [];
  highlightCount.value = 0;
  activeHighlightIndex.value = -1;
  for (const el of pageInnerRefs.values()) el.innerHTML = '';
  await setupObservers();
});

// ─── PDF Laden ───────────────────────────────────────────────────────────────

async function loadPdf(src) {
  const epoch = ++loadEpoch;

  teardownObservers();
  lastRenderWidth = 0;
  renderedPages.clear();
  renderQueue.clear();
  pageInnerRefs.clear();
  pageInfos.value   = [];
  firstPageReady.value = false;
  currentPage.value = 1;
  errorMessage.value = '';
  loadProgress.value = 0;
  loadIndeterminate.value = false;
  highlightCount.value = 0;
  activeHighlightIndex.value = -1;
  highlightTargets = [];
  highlightIdSeq = 0;

  if (activeLoadTask) { try { activeLoadTask.destroy(); } catch (_) {} activeLoadTask = null; }
  if (pdfDoc)         { try { pdfDoc.destroy(); }         catch (_) {} pdfDoc = null; }

  if (!src) return;

  isLoading.value = true;

  try {
    const bytes = await fetchPdfBytes(src, epoch);
    if (epoch !== loadEpoch) return;

    activeLoadTask = getDocument({ data: new Uint8Array(bytes.slice(0)) });
    const doc = await activeLoadTask.promise;
    if (epoch !== loadEpoch) return;

    pdfDoc = doc;
    loadProgress.value = Math.max(loadProgress.value, 92);

    const firstInfo = await readPageInfo(doc, 1);
    if (epoch !== loadEpoch) return;

    const infos = Array.from({ length: doc.numPages }, (_, index) => ({
      page: index + 1,
      width: firstInfo.width,
      height: firstInfo.height,
    }));
    infos[0] = firstInfo;
    pageInfos.value = infos;
    loadProgress.value = 100;
    isLoading.value = false;

    await setupObservers();
    emit('loaded');

    await nextTick();
    scrollToPage(props.targetPage);
    void hydrateRemainingPageInfos(doc, epoch).then(() => {
      if (epoch !== loadEpoch) return;
      void setupObservers();
    });

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
  // Die Render-Skalierung hängt allein von der Breite ab (computeScale → containerWidth).
  // Reine Höhenänderungen (Detail-Schublade auf/zu, Splitter ziehen) erfordern kein
  // Neu-Rendern – sonst würde die ganze Vorschau bei jedem Frame geleert (Flackern).
  const width = containerWidth();
  if (width === lastRenderWidth) return;
  lastRenderWidth = width;

  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => {
    resizeRaf = 0;
    renderedPages.clear();
    renderQueue.clear();
    highlightTargets = [];
    highlightCount.value = 0;
    activeHighlightIndex.value = -1;
    for (const el of pageInnerRefs.values()) el.innerHTML = '';
    setupObservers();
  });
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
  if (resizeRaf)      cancelAnimationFrame(resizeRaf);
  if (scrollRafId)    cancelAnimationFrame(scrollRafId);
  if (highlightFlashTimer) window.clearTimeout(highlightFlashTimer);
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
  /* Overlay über dem oberen Seitenrand: das Dokument scrollt dahinter durch und
     scheint durch das durchscheinende Frosted-Glas (wie die eingeklappte Leiste). */
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5px 14px;
  border-bottom: 1px solid var(--pm-drawer-border-collapsed, var(--pm-divider));
  background: var(--pm-drawer-bg-collapsed);
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  gap: 12px;
  min-height: 36px;
  box-sizing: border-box;
}

.pdf-preview__page-info {
  position: absolute;
  left: 14px;
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface) / 0.55);
  white-space: nowrap;
  min-width: 3rem;
}

.pdf-preview__match-controls {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
}

.pdf-preview__match-nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid rgba(200, 150, 0, 0.24);
  border-radius: 999px;
  background: rgba(255, 200, 0, 0.16);
  color: rgb(var(--v-theme-on-surface) / 0.72);
  cursor: pointer;
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease, opacity 120ms ease;
}

.pdf-preview__match-nav-btn:hover:not(:disabled) {
  background: rgba(255, 200, 0, 0.28);
  border-color: rgba(200, 150, 0, 0.4);
  color: rgb(var(--v-theme-on-surface) / 0.9);
}

.pdf-preview__match-nav-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.pdf-preview__match-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(255, 200, 0, 0.35);
  color: rgb(var(--v-theme-on-surface) / 0.85);
  border: 1px solid rgba(200, 150, 0, 0.3);
  white-space: nowrap;
  flex: 0 0 auto;
  text-align: center;
}

.pdf-preview__match-badge--zero {
  background: rgb(var(--v-theme-on-surface) / 0.06);
  border-color: rgb(var(--v-theme-on-surface) / 0.12);
  color: rgb(var(--v-theme-on-surface) / 0.45);
  font-weight: 400;
}

.pdf-preview__zoom-controls {
  position: absolute;
  right: 14px;
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

/* ── Viewer-Wrapper: Fade-in nach erstem Render ─────────────────────────── */
.pdf-preview__viewer {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  opacity: 0;
  position: relative;
  transition: opacity 180ms ease;
}

.pdf-preview__viewer--ready {
  opacity: 1;
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
  /* Oben Platz für die überlagernde (absolute) Toolbar */
  padding: 50px 14px 14px;
}

/* ── Einzelne Seite ─────────────────────────────────────────────────────── */
.pdf-preview__page {
  flex: 0 0 auto;
  position: relative;
  border-radius: 6px;
  overflow: hidden;
}

/* Schatten erst zeigen, sobald Seite gerendert ist (Inner-Div hat Inhalt) */
.pdf-preview__page:has(.pdf-preview__page-inner:not(:empty)) {
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

/* Suchmarkierung: <mark> (Range API, same-node) UND span.pm-highlight (cross-span) */
.pdf-preview__page-inner :deep(.textLayer mark.pm-highlight),
.pdf-preview__page-inner :deep(.textLayer span.pm-highlight) {
  background: rgba(255, 200, 0, 0.55);
  color: transparent;
  border-radius: 2px;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  padding: 0;
  margin: 0;
}

.pdf-preview__page-inner :deep(.textLayer .pm-highlight.pm-highlight--active) {
  background: rgba(255, 180, 0, 0.78);
  box-shadow: 0 0 0 1px rgba(180, 120, 0, 0.28);
}

.pdf-preview__page-inner :deep(.textLayer .pm-highlight.pm-highlight--flash) {
  animation: pdf-highlight-pop 620ms cubic-bezier(0.18, 0.9, 0.26, 1.25);
  transform-origin: center;
  will-change: transform, box-shadow;
}

@keyframes pdf-highlight-pop {
  0% {
    transform: translateY(0) scale(1);
    box-shadow: 0 0 0 1px rgba(180, 120, 0, 0.28);
  }
  38% {
    transform: translateY(-3px) scale(1.16);
    box-shadow: 0 6px 14px rgba(180, 120, 0, 0.24), 0 0 0 2px rgba(255, 190, 0, 0.48);
  }
  68% {
    transform: translateY(1px) scale(0.98);
  }
  100% {
    transform: translateY(0) scale(1);
    box-shadow: 0 0 0 1px rgba(180, 120, 0, 0.28);
  }
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
  opacity: 0;
  animation: pm-loading-appear 0s 600ms forwards;
}

@keyframes pm-loading-appear {
  to { opacity: 1; }
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

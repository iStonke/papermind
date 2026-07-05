<template>
  <div
    ref="rootEl"
    class="pdf-preview"
    :class="pdfPreviewClasses"
    :style="pdfPreviewThemeStyle"
    role="region"
    aria-label="PDF Vorschau"
    @keydown="onKeydown"
  >

    <!-- Fehlerzustand -->
    <div v-if="errorMessage" class="pdf-preview__placeholder">
      <PmEmptyState
        icon="mdi-file-document-outline"
        title="Vorschau nicht verfügbar"
        :subtitle="errorMessage"
        size="md"
      />
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
        <div class="pdf-preview__left-controls">
          <button
            v-if="enableReader"
            class="pdf-preview__tool-btn"
            :disabled="!src"
            aria-label="Im Lesemodus öffnen"
            title="Im Lesemodus öffnen (f)"
            @click="emit('open-reader')"
          >
            <v-icon size="17">mdi-arrow-expand</v-icon>
          </button>
          <span class="pdf-preview__page-info" aria-live="polite">
            {{ currentPage }} / {{ pageInfos.length }}
          </span>
        </div>

        <div class="pdf-preview__rotate-controls" role="group" aria-label="Aktive Seite drehen">
          <button
            class="pdf-preview__rotate-btn"
            :disabled="!pageInfos.length"
            aria-label="Aktive Seite nach links drehen"
            title="Aktive Seite nach links drehen"
            @click="rotateActivePage(-90)"
          >
            <v-icon size="16">mdi-rotate-left</v-icon>
          </button>
          <button
            class="pdf-preview__rotate-btn"
            :disabled="!pageInfos.length"
            aria-label="Aktive Seite nach rechts drehen"
            title="Aktive Seite nach rechts drehen"
            @click="rotateActivePage(90)"
          >
            <v-icon size="16">mdi-rotate-right</v-icon>
          </button>
        </div>

        <Transition name="pdf-preview-match">
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
            >
              <v-icon size="16">mdi-chevron-left</v-icon>
            </button>
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
            >
              <v-icon size="16">mdi-chevron-right</v-icon>
            </button>
          </div>
        </Transition>

        <div class="pdf-preview__zoom-controls" role="group" aria-label="Zoom">
          <button
            class="pdf-preview__tool-btn"
            :class="{ 'pdf-preview__tool-btn--active': magnifierEnabled }"
            :aria-pressed="magnifierEnabled"
            aria-label="Lupe"
            title="Lupe (Ausschnitt vergrößern)"
            @click="toggleMagnifier"
          >
            <v-icon size="17">mdi-magnify</v-icon>
          </button>
          <div class="pdf-preview__zoom-stepper">
            <button
              class="pdf-preview__zoom-seg"
              :disabled="!canZoomOut"
              aria-label="Verkleinern"
              @click="zoomOut"
            >
              <v-icon size="16">mdi-minus</v-icon>
            </button>
            <button
              class="pdf-preview__zoom-value"
              :class="{ 'pdf-preview__zoom-value--default': isDefaultZoom }"
              :aria-label="`Zoom ${zoomPercent} Prozent – auf 100 % zurücksetzen`"
              title="Auf 100 % zurücksetzen"
              @click="resetZoom"
            >{{ zoomPercent }}%</button>
            <button
              class="pdf-preview__zoom-seg"
              :disabled="!canZoomIn"
              aria-label="Vergrößern"
              @click="zoomIn"
            >
              <v-icon size="16">mdi-plus</v-icon>
            </button>
          </div>
        </div>
      </div>

      <!-- Seiten-Container (scrollbar) -->
      <div
        ref="pagesEl"
        class="pdf-preview__pages"
        :class="{ 'pdf-preview__pages--magnify': magnifierEnabled }"
        tabindex="0"
        @pointerdown="onPagesPointerDown"
        @pointermove="onPagesPointerMove"
        @pointerleave="onPagesPointerLeave"
        @pointerup="onPagesPointerUp"
        @wheel="onPagesWheel"
      >
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

      <!-- Lupe (folgt dem Cursor) -->
      <canvas
        v-show="magnifier.visible"
        ref="loupeEl"
        class="pdf-preview__loupe"
        :style="loupeStyle"
        aria-hidden="true"
      />

      <!-- Auswahl-Menü: erscheint über markiertem Text (nur wenn annotatable) -->
      <div
        v-if="annotatable && selectionMenu.visible"
        class="pm-sel-menu"
        :style="{ left: `${selectionMenu.x}px`, top: `${selectionMenu.y}px` }"
        @mousedown.prevent
      >
        <button
          v-for="c in ANNOT_COLORS"
          :key="c"
          class="pm-sel-menu__color"
          :class="{ 'pm-sel-menu__color--active': isSelectionColorActive(c) }"
          :style="{ background: c }"
          :aria-label="selectionColorLabel(c)"
          :aria-pressed="isSelectionColorActive(c)"
          @click="toggleAnnotationColorFromSelection(c)"
        />
        <span class="pm-sel-menu__divider" aria-hidden="true" />
        <button class="pm-sel-menu__btn" aria-label="Kommentar hinzufügen" title="Kommentar" @click="requestCommentFromSelection">
          <v-icon size="16">mdi-comment-text-outline</v-icon>
        </button>
        <button class="pm-sel-menu__btn" aria-label="Mit Dokument verknüpfen" title="Verknüpfen" @click="requestLinkFromSelection">
          <v-icon size="16">mdi-link-variant</v-icon>
        </button>
        <button class="pm-sel-menu__btn" aria-label="Auswahl kopieren" title="Kopieren" @click="copySelection">
          <v-icon size="16">mdi-content-copy</v-icon>
        </button>
      </div>
    </div>

  </div>
</template>

<script>
// Modulweiter PDF-Byte-Cache: Die Vorschau bekommt pro Dokument einen neuen :key
// und wird daher bei jedem Wechsel neu gemountet. Läge der Cache in <script setup>,
// wäre er pro Instanz und ginge jedes Mal verloren → erneuter Voll-Download. Auf
// Modulebene überlebt er die Remounts, sodass kürzlich geöffnete PDFs sofort ohne
// Netzwerk bereitstehen.
const PDF_BYTE_CACHE_MAX_ENTRIES = 6;
const pdfByteCache = new Map();
</script>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import { TextLayer } from 'pdfjs-dist';
import 'pdfjs-dist/web/pdf_viewer.css';
import Konva from 'konva';
import { useTheme } from 'vuetify';
import PmEmptyState from './PmEmptyState.vue';
import { PDF_WORKER_SRC } from '../utils/pdfWorker.js';

GlobalWorkerOptions.workerSrc = PDF_WORKER_SRC;

// ─── Props & Emits ────────────────────────────────────────────────────────────

const props = defineProps({
  src:           { type: String, default: '' },
  targetPage:    { type: Number, default: null },
  /** Text der im TextLayer hervorgehoben werden soll (z.B. citation.snippet) */
  highlightText: { type: String, default: '' },
  /** Aktiviert die Markierungsebene (Auswahl-Menü + Overlay-Highlights). */
  annotatable:   { type: Boolean, default: false },
  /** Persistierte Markierungen: [{ id, page, kind, color, rects:[{x,y,w,h}], comment }] */
  annotations:   { type: Array, default: () => [] },
  /** Aktives Werkzeug im Lesemodus: highlight | rectangle | eraser | text | pen */
  annotationTool: { type: String, default: '' },
  /** Aktive Farbe für Rechteck/Stift/Text (universelle Farbwahl in der Werkzeug-Leiste). */
  annotationColor: { type: String, default: '' },
  /** Zeigt den „Lesemodus"-Button in der Toolbar und aktiviert die Taste „f". */
  enableReader:  { type: Boolean, default: false },
});
const emit = defineEmits(['loaded', 'failed', 'create-annotation', 'delete-annotation', 'update-annotation', 'open-reader', 'request-link', 'request-comment']);
const theme = useTheme();

const pdfPreviewThemeStyle = computed(() => {
  if (theme.global.current.value.dark) {
    return {
      '--pdf-toolbar-bg': 'rgb(15 23 42 / 0.72)',
      '--pdf-toolbar-border': 'rgb(255 255 255 / 0.1)',
      '--pdf-toolbar-shadow': '0 8px 22px rgb(0 0 0 / 0.24)',
      '--pdf-toolbar-text': 'rgb(226 232 240 / 0.85)',
      '--pdf-toolbar-text-muted': 'rgb(226 232 240 / 0.68)',
      '--pdf-toolbar-icon': 'rgb(226 232 240 / 0.72)',
      '--pdf-toolbar-hover-bg': 'rgb(255 255 255 / 0.1)',
      '--pdf-toolbar-stepper-bg': 'rgb(255 255 255 / 0.07)',
      '--pdf-toolbar-divider': 'rgb(255 255 255 / 0.12)'
    };
  }
  return {
    '--pdf-toolbar-bg': 'rgb(255 255 255 / 0.94)',
    '--pdf-toolbar-border': 'rgb(203 213 225 / 0.92)',
    '--pdf-toolbar-shadow': '0 14px 34px rgb(15 23 42 / 0.12), 0 2px 8px rgb(15 23 42 / 0.08)',
    '--pdf-toolbar-text': 'rgb(31 41 55 / 0.88)',
    '--pdf-toolbar-text-muted': 'rgb(75 85 99 / 0.72)',
    '--pdf-toolbar-icon': 'rgb(71 85 105 / 0.76)',
    '--pdf-toolbar-hover-bg': 'rgb(15 23 42 / 0.07)',
    '--pdf-toolbar-stepper-bg': 'rgb(241 245 249 / 0.96)',
    '--pdf-toolbar-divider': 'rgb(148 163 184 / 0.24)'
  };
});

const activeAnnotationTool = computed(() => {
  if (!props.annotatable) return '';
  return String(props.annotationTool || '').trim();
});

const pdfPreviewClasses = computed(() => {
  const tool = activeAnnotationTool.value;
  return {
    'pdf-preview--document-ready': firstPageReady.value,
    'pdf-preview--tool-active': Boolean(tool),
    [`pdf-preview--tool-${tool}`]: Boolean(tool),
  };
});

// ─── Zoom ─────────────────────────────────────────────────────────────────────

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 3.0;
const DEFAULT_ZOOM = 1.0;
const ZOOM_BUTTON_FACTOR = 1.12;
const ZOOM_WHEEL_SENSITIVITY = 0.0025;
const ZOOM_RENDER_DEBOUNCE_MS = 240;
const ZOOM_EPSILON = 0.001;
const MAX_CACHED_PAGES = 12;
const PAGE_INFO_BATCH_SIZE = 6;
// pdfByteCache + PDF_BYTE_CACHE_MAX_ENTRIES liegen modulweit (oberer <script>-Block),
// damit sie das Neu-Mounten der Komponente überleben.

const currentZoom = ref(DEFAULT_ZOOM);
const zoomPercent = computed(() => Math.round(currentZoom.value * 100));
const isDefaultZoom = computed(() => Math.abs(currentZoom.value - DEFAULT_ZOOM) <= ZOOM_EPSILON);
const canZoomOut = computed(() => currentZoom.value > MIN_ZOOM + ZOOM_EPSILON);
const canZoomIn = computed(() => currentZoom.value < MAX_ZOOM - ZOOM_EPSILON);

let pendingZoomAnchor = null;
let gestureStartZoom = DEFAULT_ZOOM;
let gestureActive = false;
let zoomRenderTimer = 0;

function clampZoom(value) {
  if (!Number.isFinite(value)) return currentZoom.value;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
}

function zoomIn() {
  setZoom(currentZoom.value * ZOOM_BUTTON_FACTOR);
}
function zoomOut() {
  setZoom(currentZoom.value / ZOOM_BUTTON_FACTOR);
}
function resetZoom() {
  setZoom(DEFAULT_ZOOM);
}

function scheduleZoomRender() {
  if (zoomRenderTimer) window.clearTimeout(zoomRenderTimer);
  zoomRenderTimer = window.setTimeout(() => {
    zoomRenderTimer = 0;
    commitZoomRender();
  }, ZOOM_RENDER_DEBOUNCE_MS);
}

function commitZoomRender() {
  if (!pdfDoc) return;
  renderGeneration++;
  renderedPages.clear();
  renderQueue.clear();
  highlightTargets = [];
  highlightCount.value = 0;
  activeHighlightIndex.value = -1;
  void setupObservers();
}

function defaultZoomClientPoint() {
  const rect = pagesEl.value?.getBoundingClientRect();
  if (!rect) return null;
  return {
    clientX: rect.left + rect.width / 2,
    clientY: rect.top + rect.height / 2,
  };
}

function setZoom(value, anchor = null) {
  const nextZoom = clampZoom(value);
  if (Math.abs(nextZoom - currentZoom.value) <= ZOOM_EPSILON) return;
  const point = anchor && Number.isFinite(anchor.clientX) && Number.isFinite(anchor.clientY)
    ? anchor
    : defaultZoomClientPoint();
  pendingZoomAnchor = point ? captureZoomAnchor(point.clientX, point.clientY) : null;
  currentZoom.value = nextZoom;
}

function normalizeWheelDelta(event) {
  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) return event.deltaY * 16;
  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) return event.deltaY * (pagesEl.value?.clientHeight || 800);
  return event.deltaY;
}

function onPagesWheel(event) {
  if (!event.ctrlKey && !event.metaKey) return;
  event.preventDefault();
  hideMagnifier();

  const delta = normalizeWheelDelta(event);
  if (!Number.isFinite(delta) || Math.abs(delta) < 0.01) return;
  const factor = Math.exp(-delta * ZOOM_WHEEL_SENSITIVITY);
  setZoom(currentZoom.value * factor, { clientX: event.clientX, clientY: event.clientY });
}

function onGestureStart(event) {
  event.preventDefault();
  gestureActive = true;
  gestureStartZoom = currentZoom.value;
  pendingZoomAnchor = captureZoomAnchor(event.clientX, event.clientY);
  hideMagnifier();
}

function onGestureChange(event) {
  if (!gestureActive) return;
  event.preventDefault();
  const scale = Number(event.scale || 1);
  setZoom(gestureStartZoom * scale, { clientX: event.clientX, clientY: event.clientY });
}

function onGestureEnd(event) {
  if (!gestureActive) return;
  event.preventDefault();
  gestureActive = false;
}

function attachGestureZoomListeners(el) {
  el.addEventListener('gesturestart', onGestureStart, { passive: false });
  el.addEventListener('gesturechange', onGestureChange, { passive: false });
  el.addEventListener('gestureend', onGestureEnd, { passive: false });
}

function detachGestureZoomListeners(el) {
  el?.removeEventListener('gesturestart', onGestureStart);
  el?.removeEventListener('gesturechange', onGestureChange);
  el?.removeEventListener('gestureend', onGestureEnd);
}

function clampScroll(value, max) {
  return Math.min(Math.max(0, value), Math.max(0, max));
}

function captureZoomAnchor(clientX, clientY) {
  const container = pagesEl.value;
  if (!container) return null;

  const containerRect = container.getBoundingClientRect();
  const safeClientX = Number.isFinite(clientX) ? clientX : containerRect.left + containerRect.width / 2;
  const safeClientY = Number.isFinite(clientY) ? clientY : containerRect.top + containerRect.height / 2;
  const viewportX = Math.min(Math.max(safeClientX - containerRect.left, 0), container.clientWidth);
  const viewportY = Math.min(Math.max(safeClientY - containerRect.top, 0), container.clientHeight);
  const pointedEl = document.elementFromPoint(safeClientX, safeClientY);
  const pageEl = pointedEl?.closest?.('.pdf-preview__page');

  if (pageEl && container.contains(pageEl)) {
    const pageRect = pageEl.getBoundingClientRect();
    return {
      type: 'page',
      page: Number(pageEl.dataset.page),
      ratioX: Math.min(Math.max((safeClientX - pageRect.left) / Math.max(1, pageRect.width), 0), 1),
      ratioY: Math.min(Math.max((safeClientY - pageRect.top) / Math.max(1, pageRect.height), 0), 1),
      viewportX,
      viewportY,
    };
  }

  return {
    type: 'container',
    ratioX: (container.scrollLeft + viewportX) / Math.max(1, container.scrollWidth),
    ratioY: (container.scrollTop + viewportY) / Math.max(1, container.scrollHeight),
    viewportX,
    viewportY,
  };
}

function restoreZoomAnchor(anchor) {
  const container = pagesEl.value;
  if (!container || !anchor) return;

  if (anchor.type === 'page') {
    const pageEl = container.querySelector(`.pdf-preview__page[data-page="${anchor.page}"]`);
    if (pageEl) {
      container.scrollLeft = clampScroll(
        pageEl.offsetLeft + pageEl.offsetWidth * anchor.ratioX - anchor.viewportX,
        container.scrollWidth - container.clientWidth
      );
      container.scrollTop = clampScroll(
        pageEl.offsetTop + pageEl.offsetHeight * anchor.ratioY - anchor.viewportY,
        container.scrollHeight - container.clientHeight
      );
      recalcCurrentPage();
      return;
    }
  }

  container.scrollLeft = clampScroll(
    container.scrollWidth * anchor.ratioX - anchor.viewportX,
    container.scrollWidth - container.clientWidth
  );
  container.scrollTop = clampScroll(
    container.scrollHeight * anchor.ratioY - anchor.viewportY,
    container.scrollHeight - container.clientHeight
  );
  recalcCurrentPage();
}

// ─── Lupe ───────────────────────────────────────────────────────────────────

const MAGNIFIER_WIDTH = 260;
const MAGNIFIER_HEIGHT = 180;
const MAGNIFIER_FACTOR = 2.25;

const loupeEl = ref(null);
const magnifierEnabled = ref(false);
const magnifier = ref({ visible: false, x: 0, y: 0 });

const loupeStyle = computed(() => ({
  width: `${MAGNIFIER_WIDTH}px`,
  height: `${MAGNIFIER_HEIGHT}px`,
  transform: `translate(${Math.round(magnifier.value.x - MAGNIFIER_WIDTH / 2)}px, ${Math.round(magnifier.value.y - MAGNIFIER_HEIGHT / 2)}px)`,
}));

function toggleMagnifier() {
  magnifierEnabled.value = !magnifierEnabled.value;
  if (!magnifierEnabled.value) hideMagnifier();
}

function hideMagnifier() {
  if (magnifier.value.visible) magnifier.value = { ...magnifier.value, visible: false };
}

function onMagnifierPointerMove(event) {
  if (!magnifierEnabled.value || event.pointerType === 'touch') {
    hideMagnifier();
    return;
  }
  const container = pagesEl.value;
  const pageEl = event.target?.closest?.('.pdf-preview__page');
  const canvas = pageEl?.querySelector('canvas');
  if (!container || !(canvas instanceof HTMLCanvasElement) || !canvas.width) {
    hideMagnifier();
    return;
  }

  const canvasRect = canvas.getBoundingClientRect();
  const localX = event.clientX - canvasRect.left;
  const localY = event.clientY - canvasRect.top;
  if (localX < 0 || localY < 0 || localX > canvasRect.width || localY > canvasRect.height) {
    hideMagnifier();
    return;
  }

  const containerRect = container.getBoundingClientRect();
  magnifier.value = {
    visible: true,
    x: event.clientX - containerRect.left,
    y: event.clientY - containerRect.top,
  };

  drawLoupe(canvas, canvasRect, localX, localY);
}

function drawLoupe(canvas, canvasRect, localX, localY) {
  const loupe = loupeEl.value;
  if (!loupe) return;

  const dpr = window.devicePixelRatio || 1;
  const targetW = Math.round(MAGNIFIER_WIDTH * dpr);
  const targetH = Math.round(MAGNIFIER_HEIGHT * dpr);
  if (loupe.width !== targetW)  loupe.width = targetW;
  if (loupe.height !== targetH) loupe.height = targetH;

  const ctx = loupe.getContext('2d');
  if (!ctx) return;

  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, MAGNIFIER_WIDTH, MAGNIFIER_HEIGHT);
  // Weißer Untergrund (Bereiche außerhalb der Seite bleiben so nicht transparent)
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, MAGNIFIER_WIDTH, MAGNIFIER_HEIGHT);

  // Verhältnis von Canvas-Auflösung zu Anzeigegröße
  const ratioX = canvas.width / canvasRect.width;
  const ratioY = canvas.height / canvasRect.height;

  // Quellausschnitt (in Canvas-Pixeln), zentriert auf den Cursor
  const srcW = (MAGNIFIER_WIDTH / MAGNIFIER_FACTOR) * ratioX;
  const srcH = (MAGNIFIER_HEIGHT / MAGNIFIER_FACTOR) * ratioY;
  let srcX = localX * ratioX - srcW / 2;
  let srcY = localY * ratioY - srcH / 2;

  // Skalierung Quelle → Ziel
  const kx = MAGNIFIER_WIDTH / srcW;
  const ky = MAGNIFIER_HEIGHT / srcH;

  // Quell-/Zielrechteck an Canvas-Ränder klippen (Cursor bleibt zentriert)
  let sx = srcX, sy = srcY, sw = srcW, sh = srcH;
  let dx = 0, dy = 0, dw = MAGNIFIER_WIDTH, dh = MAGNIFIER_HEIGHT;
  if (sx < 0) { dx = -sx * kx; dw -= dx; sw += sx; sx = 0; }
  if (sy < 0) { dy = -sy * ky; dh -= dy; sh += sy; sy = 0; }
  if (sx + sw > canvas.width)  { const over = sx + sw - canvas.width;  sw -= over; dw -= over * kx; }
  if (sy + sh > canvas.height) { const over = sy + sh - canvas.height; sh -= over; dh -= over * ky; }

  if (sw > 0 && sh > 0) {
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(canvas, sx, sy, sw, sh, dx, dy, dw, dh);
  }
  ctx.restore();
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
const pageRotations = ref({}); // pageNum -> zusätzliche Rotation in Grad

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
let renderGeneration = 0;
const renderQueue  = new Set();
let highlightTargets = [];

/** Imperative Refs: pageNum → inneres HTMLElement */
const pageInnerRefs = new Map();

function setInnerRef(el, pageNum) {
  if (el) pageInnerRefs.set(pageNum, el);
  else    pageInnerRefs.delete(pageNum);
}

/**
 * Konva-Stage pro Seite für die interaktiven Werkzeuge Rechteck/Stift/Text:
 * pageNum → { stage, layer, containerEl, widthPx, heightPx }. Übernimmt Ziehen/
 * Skalieren/Hit-Testing von einer erprobten Canvas-Bibliothek statt eigener
 * Pointer-Mathematik (die für Rechteck/Stift/Text bei echten Mausgesten nicht
 * zuverlässig funktionierte).
 */
const konvaStages = new Map();

// ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

function containerWidth() {
  return Math.max(340, (pagesEl.value?.clientWidth || 900));
}

function normalizeRotation(value) {
  return ((Number(value) % 360) + 360) % 360;
}

function pageRotation(pageNum) {
  return normalizeRotation(pageRotations.value[pageNum] || 0);
}

function visualPageDimensions(info) {
  const rotation = pageRotation(info.page);
  if (rotation === 90 || rotation === 270) {
    return { width: info.height, height: info.width };
  }
  return { width: info.width, height: info.height };
}

function computeScale(info) {
  const maxW = Math.min(containerWidth() - 28, 980);
  const visual = visualPageDimensions(info);
  const base = maxW / visual.width;
  return Math.max(0.2, base * currentZoom.value);
}

function pageStyle(info) {
  const scale = computeScale(info);
  const visual = visualPageDimensions(info);
  return {
    width:  `${Math.floor(visual.width  * scale)}px`,
    height: `${Math.floor(visual.height * scale)}px`,
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

// ─── Markierungsebene (Annotations) ─────────────────────────────────────────
// Highlights liegen als eigene Overlay-Ebene ZWISCHEN Canvas und TextLayer:
// so bleibt der (transparente) TextLayer oben selektierbar, die Farbe scheint
// durch. Das Original-PDF wird nie verändert.

const ANNOT_COLORS = ['#FAC775', '#9FE1CB', '#F4C0D1', '#B5D4F4'];
const DEFAULT_ANNOT_COLOR = ANNOT_COLORS[0];
const COMMENT_ANNOTATION_COLOR = DEFAULT_ANNOT_COLOR;
/** Fallback, falls DocumentReader (noch) keine Farbe durchreicht. */
const DEFAULT_DRAWING_COLOR = '#0EA5E9';

/** Aktuell gewählte Farbe für Rechteck/Stift/Text (universelle Farbwahl). */
const activeDrawColor = computed(() => props.annotationColor || DEFAULT_DRAWING_COLOR);

function withAlpha(hexColor, alpha) {
  const hex = String(hexColor || '').replace('#', '');
  if (hex.length !== 6) return hexColor;
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

const selectionMenu = ref({ visible: false, x: 0, y: 0, activeColor: '' });
let selectionDraft = null; // { page, rects:[{x,y,w,h}], quote, annotations:[annotation] }
let konvaDraft = null; // laufender Rechteck-/Stift-Entwurf: { type, page, entry, node, ... }
let textDraft = null; // laufende Textbox: { pageNum, entry, rect, transformer, inputEl, commit, committed }
let suppressSelectionAfterPointer = false;

function annotationsForPage(pageNum) {
  return (props.annotations || []).filter((a) => Number(a.page) === pageNum);
}

function rectsOverlap(a, b) {
  if (!a || !b) return false;
  const epsilon = 0.002;
  return (
    a.x < b.x + b.w + epsilon &&
    a.x + a.w + epsilon > b.x &&
    a.y < b.y + b.h + epsilon &&
    a.y + a.h + epsilon > b.y
  );
}

function rectForRotation(rect, rotation) {
  const r = normalizeRotation(rotation);
  const x = Number(rect.x || 0);
  const y = Number(rect.y || 0);
  const w = Number(rect.w || 0);
  const h = Number(rect.h || 0);
  if (r === 90) return { x: 1 - y - h, y: x, w: h, h: w };
  if (r === 180) return { x: 1 - x - w, y: 1 - y - h, w, h };
  if (r === 270) return { x: y, y: 1 - x - w, w: h, h: w };
  return { x, y, w, h };
}

function rectFromRotation(rect, rotation) {
  return rectForRotation(rect, 360 - normalizeRotation(rotation));
}

function pointForRotation(point, rotation) {
  const rect = rectForRotation({ x: point.x, y: point.y, w: 0, h: 0 }, rotation);
  return { x: rect.x, y: rect.y };
}

function pointFromRotation(point, rotation) {
  return pointForRotation(point, 360 - normalizeRotation(rotation));
}

function normalizedPagePointFromEvent(event) {
  const pageEl = event.target?.closest?.('.pdf-preview__page');
  const pageNum = Number(pageEl?.dataset.page || 0);
  const innerEl = pageInnerRefs.get(pageNum);
  if (!innerEl) return null;

  const innerRect = innerEl.getBoundingClientRect();
  if (!innerRect.width || !innerRect.height) return null;
  if (
    event.clientX < innerRect.left ||
    event.clientX > innerRect.right ||
    event.clientY < innerRect.top ||
    event.clientY > innerRect.bottom
  ) {
    return null;
  }

  const clamp = (value) => Math.min(1, Math.max(0, value));
  return {
    page: pageNum,
    innerEl,
    x: clamp((event.clientX - innerRect.left) / innerRect.width),
    y: clamp((event.clientY - innerRect.top) / innerRect.height),
  };
}

function rectFromPoints(startX, startY, endX, endY) {
  const x = Math.min(startX, endX);
  const y = Math.min(startY, endY);
  return {
    x,
    y,
    w: Math.max(0, Math.max(startX, endX) - x),
    h: Math.max(0, Math.max(startY, endY) - y),
  };
}

function removeTextDraft() {
  if (!textDraft) return;
  textDraft.transformer?.destroy();
  textDraft.titlebar?.destroy();
  textDraft.grip?.destroy();
  textDraft.rect?.destroy();
  textDraft.inputEl?.remove();
  textDraft.entry?.layer?.batchDraw();
  textDraft = null;
}

/** Verwirft einen laufenden Rechteck-/Stift-Entwurf (Esc / Werkzeugwechsel). */
function cancelKonvaDraft() {
  if (!konvaDraft) return;
  konvaDraft.node?.destroy();
  konvaDraft.entry?.layer?.batchDraw();
  konvaDraft = null;
}

/**
 * Bricht einen laufenden Rechteck-/Stift-/Text-Entwurf per Esc ab, BEVOR das
 * Ereignis den Lesemodus (DocumentReader) erreicht — sonst schließt Esc dort
 * versehentlich den ganzen Lesemodus statt nur den Entwurf zu verwerfen.
 * Capture-Phase, damit es unabhängig von der Mount-Reihenfolge zuerst greift.
 */
function onWindowKeydownCapture(event) {
  if (event.key !== 'Escape') return;
  if (konvaDraft) {
    cancelKonvaDraft();
  } else if (textDraft) {
    removeTextDraft();
  } else {
    return;
  }
  // stopPropagation() allein reicht nicht: DocumentReader registriert seinen
  // Esc-Handler ebenfalls direkt auf window, und andere Listener DESSELBEN
  // Ziels feuern trotz stopPropagation weiter — nur stopImmediatePropagation
  // verhindert, dass der Lesemodus sich zusätzlich schließt.
  event.preventDefault();
  event.stopImmediatePropagation();
}

onMounted(() => {
  window.addEventListener('keydown', onWindowKeydownCapture, true);
});

// ─── Konva-Ebene: Rechteck/Stift/Text ──────────────────────────────────────────
// Zeichnen (Ziehen/Skalieren/Hit-Testing) übernimmt Konva statt eigener
// Pointer-Mathematik, die sich bei echten Mausgesten als unzuverlässig erwiesen
// hat. Eine Stage pro Seite, exakt über dem Seiten-Canvas positioniert;
// Koordinaten sind Stage-lokale CSS-Pixel (== Seitengröße bei aktuellem Zoom)
// und werden beim Speichern auf 0–1 normalisiert (wie der Rest der Annotationen).

const TEXT_DRAFT_DEFAULT_W = 200;
const TEXT_DRAFT_DEFAULT_H = 64;
const TEXT_DRAFT_MIN_W = 90;
const TEXT_DRAFT_MIN_H = 32;
const TEXT_BOX_INSET = 6; // Rand um die <textarea>, damit Transformer-Anfasser klickbar bleiben
const PEN_DRAFT_STROKE_WIDTH = 3;
const PEN_HIT_STROKE_WIDTH = 34; // großzügige, unsichtbare Trefferfläche zum Radieren dünner Linien

function destroyKonvaStage(pageNum) {
  const entry = konvaStages.get(pageNum);
  if (!entry) return;
  if (konvaDraft?.page === pageNum) konvaDraft = null;
  if (textDraft?.pageNum === pageNum) removeTextDraft();
  entry.stage.destroy();
  entry.containerEl.remove();
  konvaStages.delete(pageNum);
}

function ensureKonvaStage(pageNum, innerEl, widthPx, heightPx) {
  destroyKonvaStage(pageNum);

  const containerEl = document.createElement('div');
  containerEl.className = 'pm-konva-layer';
  const textLayerEl = innerEl.querySelector('.textLayer');
  if (textLayerEl) innerEl.insertBefore(containerEl, textLayerEl);
  else innerEl.appendChild(containerEl);

  const stage = new Konva.Stage({ container: containerEl, width: widthPx, height: heightPx });
  const layer = new Konva.Layer();
  stage.add(layer);

  const entry = { stage, layer, containerEl, widthPx, heightPx };
  konvaStages.set(pageNum, entry);
  attachStageDraftHandlers(pageNum, entry);
  return entry;
}

/** Rechteck/Stift/Text-Werkzeug per Klick/Drag auf der Stage der jeweiligen Seite. */
function attachStageDraftHandlers(pageNum, entry) {
  const { stage } = entry;

  stage.on('mousedown touchstart', (e) => {
    const tool = activeAnnotationTool.value;
    if (tool === 'rectangle') {
      const pos = stage.getPointerPosition();
      if (pos) startKonvaRectangleDraft(pageNum, entry, pos);
    } else if (tool === 'pen') {
      const pos = stage.getPointerPosition();
      if (pos) startKonvaPenDraft(pageNum, entry, pos);
    } else if (tool === 'text') {
      // Klick auf die bereits offene Box, ihre Griffleiste/Anfasser oder eine
      // bestehende (jederzeit verschiebbare) Textnotiz: Konva übernimmt das
      // Ziehen selbst, hier keine neue Box daneben anlegen.
      const hitsOwnDraft = textDraft && (
        e.target === textDraft.rect
        || e.target === textDraft.titlebar
        || e.target === textDraft.grip
        || e.target?.getParent?.() === textDraft.transformer
      );
      const hitsExistingTextAnnotation = e.target?.getParent?.()?.getClassName?.() === 'Label';
      if (hitsOwnDraft || hitsExistingTextAnnotation) return;
      const pos = stage.getPointerPosition();
      if (pos) startKonvaTextDraft(pageNum, entry, pos);
    }
  });

  stage.on('mousemove touchmove', () => {
    if (!konvaDraft || konvaDraft.page !== pageNum) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    if (konvaDraft.type === 'rectangle') updateKonvaRectangleDraft(pos);
    else if (konvaDraft.type === 'pen') updateKonvaPenDraft(pos);
  });

  stage.on('mouseup touchend', () => {
    if (!konvaDraft || konvaDraft.page !== pageNum) return;
    if (konvaDraft.type === 'rectangle') finishKonvaRectangleDraft();
    else if (konvaDraft.type === 'pen') finishKonvaPenDraft();
  });
}

function startKonvaRectangleDraft(pageNum, entry, pos) {
  cancelKonvaDraft();
  const color = activeDrawColor.value;
  const rect = new Konva.Rect({
    x: pos.x,
    y: pos.y,
    width: 0,
    height: 0,
    stroke: color,
    strokeWidth: 2,
    dash: [5, 4],
    fill: withAlpha(color, 0.12),
    listening: false,
  });
  entry.layer.add(rect);
  entry.layer.batchDraw();
  konvaDraft = { type: 'rectangle', page: pageNum, entry, node: rect, startX: pos.x, startY: pos.y };
}

function updateKonvaRectangleDraft(pos) {
  const { node, startX, startY, entry } = konvaDraft;
  const x = Math.min(startX, pos.x);
  const y = Math.min(startY, pos.y);
  node.position({ x, y });
  node.size({ width: Math.abs(pos.x - startX), height: Math.abs(pos.y - startY) });
  entry.layer.batchDraw();
}

function finishKonvaRectangleDraft() {
  const { node, entry, page } = konvaDraft;
  const visibleRect = {
    x: node.x() / entry.widthPx,
    y: node.y() / entry.heightPx,
    w: node.width() / entry.widthPx,
    h: node.height() / entry.heightPx,
  };
  node.destroy();
  entry.layer.batchDraw();
  konvaDraft = null;
  if (visibleRect.w < 0.006 || visibleRect.h < 0.006) return;

  emit('create-annotation', {
    page,
    kind: 'rectangle',
    color: activeDrawColor.value,
    rects: [rectFromRotation(visibleRect, pageRotation(page))],
    quote: null,
  });
}

function startKonvaPenDraft(pageNum, entry, pos) {
  cancelKonvaDraft();
  const line = new Konva.Line({
    points: [pos.x, pos.y],
    stroke: activeDrawColor.value,
    strokeWidth: PEN_DRAFT_STROKE_WIDTH,
    lineCap: 'round',
    lineJoin: 'round',
    tension: 0.3,
    listening: false,
  });
  entry.layer.add(line);
  entry.layer.batchDraw();
  konvaDraft = { type: 'pen', page: pageNum, entry, node: line, points: [{ x: pos.x, y: pos.y }] };
}

function updateKonvaPenDraft(pos) {
  const points = konvaDraft.points;
  const last = points[points.length - 1];
  if (last && Math.hypot(pos.x - last.x, pos.y - last.y) < 1.5) return;
  points.push({ x: pos.x, y: pos.y });
  konvaDraft.node.points(points.flatMap((p) => [p.x, p.y]));
  konvaDraft.entry.layer.batchDraw();
}

function finishKonvaPenDraft() {
  const { entry, page, points, node } = konvaDraft;
  node.destroy();
  entry.layer.batchDraw();
  konvaDraft = null;
  if (points.length < 2) return;

  const norm = points.map((p) => ({ x: p.x / entry.widthPx, y: p.y / entry.heightPx }));
  let minX = 1, minY = 1, maxX = 0, maxY = 0;
  for (const p of norm) {
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }
  const pad = 0.006;
  const bounds = {
    x: Math.max(0, minX - pad),
    y: Math.max(0, minY - pad),
    w: Math.min(1, maxX + pad) - Math.max(0, minX - pad),
    h: Math.min(1, maxY + pad) - Math.max(0, minY - pad),
  };
  if (bounds.w < 0.004 || bounds.h < 0.004) return;

  emit('create-annotation', {
    page,
    kind: 'pen',
    color: activeDrawColor.value,
    rects: [rectFromRotation(bounds, pageRotation(page))],
    quote: JSON.stringify({
      type: 'pen',
      points: norm.map((p) => pointFromRotation(p, pageRotation(page))),
    }),
  });
}

const TEXT_TITLEBAR_H = 20; // Griffleiste oben an der Box — großer, eindeutiger Zieh-Bereich

/**
 * Textbox frei positionierbar/skalierbar: eine Griffleiste oben (einzige
 * Zieh-Fläche, groß genug für echte Mausbedienung — ein schmaler Rand allein
 * war in der Praxis kaum zu treffen) + Konva.Rect+Transformer für die Größe,
 * dazu eine echte <textarea> (leicht eingerückt, damit die Transformer-
 * Anfasser am Rand klickbar bleiben) fürs Tippen darüber.
 */
function startKonvaTextDraft(pageNum, entry, pos) {
  // Klick woanders während eine Box offen ist übernimmt deren Text (verwirft
  // ihn NICHT) — nur Esc verwirft explizit, siehe onWindowKeydownCapture.
  if (textDraft) textDraft.commit();

  const color = activeDrawColor.value;
  const width = TEXT_DRAFT_DEFAULT_W;
  const height = TEXT_DRAFT_DEFAULT_H;
  const x = Math.min(Math.max(0, entry.widthPx - width), pos.x);
  const y = Math.min(Math.max(0, entry.heightPx - height - TEXT_TITLEBAR_H), pos.y);

  const titlebar = new Konva.Rect({
    x, y, width, height: TEXT_TITLEBAR_H,
    fill: color,
    cornerRadius: [4, 4, 0, 0],
    draggable: true,
  });
  const grip = new Konva.Text({
    x, y, width, height: TEXT_TITLEBAR_H,
    text: '•••',
    align: 'center',
    verticalAlign: 'middle',
    fontSize: 11,
    fill: 'rgba(255, 255, 255, 0.85)',
    listening: false,
  });
  const body = new Konva.Rect({
    x, y: y + TEXT_TITLEBAR_H, width, height,
    fill: 'rgba(255, 255, 255, 0.92)',
    stroke: color,
    strokeWidth: 1,
    cornerRadius: [0, 0, 4, 4],
  });
  entry.layer.add(body);
  entry.layer.add(titlebar);
  entry.layer.add(grip);

  const transformer = new Konva.Transformer({
    nodes: [body],
    rotateEnabled: false,
    enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'middle-left', 'middle-right', 'top-center', 'bottom-center'],
    boundBoxFunc: (oldBox, newBox) => (
      (newBox.width < TEXT_DRAFT_MIN_W || newBox.height < TEXT_DRAFT_MIN_H) ? oldBox : newBox
    ),
  });
  entry.layer.add(transformer);
  // Synchron zeichnen: die Griffleiste muss SOFORT ziehbar sein, batchDraw()
  // verzögert den Hit-Graph bis zum nächsten Animation-Frame (siehe
  // renderKonvaAnnotations für dieselbe Problematik beim Radierer).
  entry.layer.draw();

  const inputEl = document.createElement('textarea');
  inputEl.className = 'pm-text-draft';
  entry.containerEl.parentElement.appendChild(inputEl);

  const syncTitlebarToBody = () => {
    titlebar.position({ x: body.x(), y: body.y() - TEXT_TITLEBAR_H });
    titlebar.width(body.width());
    grip.position(titlebar.position());
    grip.width(body.width());
  };
  const syncInputToBody = () => {
    inputEl.style.left   = `${body.x() + TEXT_BOX_INSET}px`;
    inputEl.style.top    = `${body.y() + TEXT_BOX_INSET}px`;
    inputEl.style.width  = `${Math.max(0, body.width()  - TEXT_BOX_INSET * 2)}px`;
    inputEl.style.height = `${Math.max(0, body.height() - TEXT_BOX_INSET * 2)}px`;
  };
  syncInputToBody();

  titlebar.on('mouseenter', () => { entry.stage.container().style.cursor = 'move'; });
  titlebar.on('mouseleave', () => { entry.stage.container().style.cursor = ''; });
  titlebar.on('dragmove', () => {
    body.position({ x: titlebar.x(), y: titlebar.y() + TEXT_TITLEBAR_H });
    syncTitlebarToBody();
    syncInputToBody();
  });
  body.on('transform', () => {
    // Standard-Konva-Rezept: Skalierung sofort in reale Breite/Höhe einrechnen
    // und zurücksetzen, sonst verzerrt sich die Box bei weiteren Resizes.
    body.width(Math.max(TEXT_DRAFT_MIN_W, body.width() * body.scaleX()));
    body.height(Math.max(TEXT_DRAFT_MIN_H, body.height() * body.scaleY()));
    body.scaleX(1);
    body.scaleY(1);
    syncTitlebarToBody();
    syncInputToBody();
  });

  const draft = {
    pageNum, entry, rect: body, titlebar, grip, transformer, inputEl, committed: false,
    commit: () => {
      if (draft.committed) return;
      draft.committed = true;
      const text = inputEl.value.trim();
      const visibleRect = {
        x: body.x() / entry.widthPx,
        y: body.y() / entry.heightPx,
        w: body.width() / entry.widthPx,
        h: body.height() / entry.heightPx,
      };
      removeTextDraft();
      if (!text) return;
      emit('create-annotation', {
        page: pageNum,
        kind: 'text',
        color,
        rects: [rectFromRotation(visibleRect, pageRotation(pageNum))],
        quote: text,
      });
    },
  };
  textDraft = draft;

  inputEl.addEventListener('keydown', (keyboardEvent) => {
    if (keyboardEvent.key === 'Enter' && !keyboardEvent.shiftKey) {
      keyboardEvent.preventDefault();
      draft.commit();
    }
    // Escape wird zentral von onWindowKeydownCapture behandelt (verwirft die Box).
  });
  requestAnimationFrame(() => inputEl.focus());
}

/** Zeichnet die persistierten Rechteck-/Stift-/Text-Annotationen einer Seite in Konva. */
function renderKonvaAnnotations(pageNum) {
  const entry = konvaStages.get(pageNum);
  if (!entry) return;
  const { layer, widthPx, heightPx } = entry;
  layer.destroyChildren();

  const eraseIfActive = (annotId) => (e) => {
    if (activeAnnotationTool.value !== 'eraser') return;
    e.cancelBubble = true;
    emit('delete-annotation', annotId);
  };

  for (const annot of annotationsForPage(pageNum)) {
    const color = annot.color || DEFAULT_ANNOT_COLOR;

    if (annot.kind === 'rectangle') {
      const rect = annot.rects?.[0];
      if (!rect) continue;
      const vis = rectForRotation(rect, pageRotation(pageNum));
      const node = new Konva.Rect({
        x: vis.x * widthPx,
        y: vis.y * heightPx,
        width: vis.w * widthPx,
        height: vis.h * heightPx,
        stroke: color,
        strokeWidth: 2,
        // Ohne fill zählt bei Konva nur der 2px-Rand als Trefferfläche —
        // die (unsichtbare) Füllung macht das ganze Rechteck klickbar/radierbar.
        fill: withAlpha(color, 0.001),
      });
      node.on('mousedown touchstart', eraseIfActive(annot.id));
      layer.add(node);
    } else if (annot.kind === 'pen') {
      let payload = null;
      try { payload = JSON.parse(annot.quote || ''); } catch (_) { payload = null; }
      const points = Array.isArray(payload?.points) ? payload.points : [];
      if (points.length < 2) continue;
      const flat = points
        .map((p) => pointForRotation(p, pageRotation(pageNum)))
        .flatMap((p) => [p.x * widthPx, p.y * heightPx]);
      const node = new Konva.Line({
        points: flat,
        stroke: color,
        strokeWidth: PEN_DRAFT_STROKE_WIDTH,
        lineCap: 'round',
        lineJoin: 'round',
        hitStrokeWidth: PEN_HIT_STROKE_WIDTH,
      });
      node.on('mousedown touchstart', eraseIfActive(annot.id));
      layer.add(node);
    } else if (annot.kind === 'text') {
      const rect = annot.rects?.[0];
      if (!rect) continue;
      const vis = rectForRotation(rect, pageRotation(pageNum));
      const label = new Konva.Label({
        x: vis.x * widthPx,
        y: vis.y * heightPx,
        // Bleibt jederzeit verschiebbar, solange das Text-Werkzeug aktiv ist —
        // kein Rahmen mehr nach dem Verfassen, nur ein dezenter Hintergrund
        // für Lesbarkeit (kein stroke/strokeWidth auf dem Tag).
        draggable: activeAnnotationTool.value === 'text',
      });
      label.add(new Konva.Tag({ fill: 'rgba(255, 255, 255, 0.68)', cornerRadius: 3 }));
      label.add(new Konva.Text({
        text: annot.quote || '',
        width: Math.max(TEXT_DRAFT_MIN_W, vis.w * widthPx),
        padding: 4,
        fill: color,
        fontSize: 14,
        fontStyle: '500',
        wrap: 'word',
      }));
      label.on('mousedown touchstart', eraseIfActive(annot.id));
      label.on('mouseenter', () => {
        if (label.draggable()) entry.stage.container().style.cursor = 'move';
      });
      label.on('mouseleave', () => { entry.stage.container().style.cursor = ''; });
      label.on('dragend', () => {
        const visibleRect = {
          x: label.x() / widthPx,
          y: label.y() / heightPx,
          w: label.width() / widthPx,
          h: label.height() / heightPx,
        };
        emit('update-annotation', annot.id, {
          rects: [rectFromRotation(visibleRect, pageRotation(pageNum))],
        });
      });
      layer.add(label);
    }
  }

  // Synchron zeichnen (statt batchDraw/rAF): sonst ist der Hit-Graph beim
  // ersten Klick direkt nach dem Rendern noch nicht aktuell und der Radierer
  // trifft nichts — batchDraw() verzögert sich in Hintergrund-Tabs/CDP-
  // gesteuerten Browsern spürbar, da requestAnimationFrame dort gedrosselt wird.
  layer.draw();
}

function annotationsForSelection(pageNum, selectionRects) {
  const items = [];
  for (const annot of annotationsForPage(pageNum)) {
    if (!annot?.id) continue;
    const annotRects = Array.isArray(annot.rects) ? annot.rects : [];
    if (annotRects.some((annotRect) => selectionRects.some((selRect) => rectsOverlap(annotRect, selRect)))) {
      items.push(annot);
    }
  }
  return items;
}

function normalizedColor(color) {
  return String(color || DEFAULT_ANNOT_COLOR).trim().toLowerCase();
}

function isPureHighlight(annot) {
  return annot?.kind === 'highlight' && !annot.comment && !annot.target_document_id && !annot.target_url;
}

function highlightAnnotationsForSelection() {
  return (selectionDraft?.annotations || []).filter(isPureHighlight);
}

function activeSelectionColor(overlappingAnnotations) {
  const colors = new Set(overlappingAnnotations.filter(isPureHighlight).map((annot) => normalizedColor(annot.color)));
  return colors.size === 1 ? [...colors][0] : '';
}

function isSelectionColorActive(color) {
  return Boolean(selectionMenu.value.activeColor) && selectionMenu.value.activeColor === normalizedColor(color);
}

function selectionColorLabel(color) {
  if (isSelectionColorActive(color)) return 'Markierung entfernen';
  return highlightAnnotationsForSelection().length ? 'Markierung umfärben' : 'Mit dieser Farbe markieren';
}

/** Zeichnet die Overlay-Rechtecke einer Seite (idempotent: alte Ebene ersetzt). */
/**
 * Zeichnet Highlight/Unterstreichung/Verknüpfung/Notiz als DOM-Overlay
 * (unverändert). Rechteck/Stift/Text laufen separat über Konva, siehe
 * renderKonvaAnnotations — die brauchen echtes Ziehen/Skalieren/Hit-Testing,
 * das eine DOM-Ebene mit pointer-events:none nicht bieten kann.
 */
function applyAnnotationsToPage(innerEl, pageNum) {
  if (!innerEl) return;
  innerEl.querySelector('.pm-annot-layer')?.remove();

  const items = annotationsForPage(pageNum).filter(
    (annot) => annot.kind !== 'rectangle' && annot.kind !== 'pen' && annot.kind !== 'text',
  );
  if (!items.length) return;

  const layer = document.createElement('div');
  layer.className = 'pm-annot-layer';

  for (const annot of items) {
    const color = annot.color || DEFAULT_ANNOT_COLOR;
    for (const rect of annot.rects || []) {
      const visibleRect = rectForRotation(rect, pageRotation(pageNum));
      const el = document.createElement('div');
      el.className = 'pm-annot-rect';
      el.dataset.annotId = annot.id;
      el.style.left   = `${visibleRect.x * 100}%`;
      el.style.top    = `${visibleRect.y * 100}%`;
      el.style.width  = `${visibleRect.w * 100}%`;
      el.style.height = `${visibleRect.h * 100}%`;
      if (annot.kind === 'underline') {
        el.classList.add('pm-annot-rect--underline');
        el.style.borderBottomColor = color;
      } else {
        el.style.background = color;
        if (annot.kind === 'link') el.classList.add('pm-annot-rect--link');
      }
      if (annot.comment) el.title = annot.comment;
      else if (annot.kind === 'link' && annot.target_document_title) el.title = `→ ${annot.target_document_title}`;
      layer.appendChild(el);
    }
  }

  // Ebene VOR den TextLayer hängen, damit Text oben selektierbar bleibt.
  const textLayer = innerEl.querySelector('.textLayer');
  if (textLayer) innerEl.insertBefore(layer, textLayer);
  else innerEl.appendChild(layer);
}

/** Aktualisiert alle gerenderten Seiten (z.B. nach Änderung der annotations-Prop). */
function redrawAllAnnotations() {
  for (const [pageNum, el] of pageInnerRefs.entries()) {
    if (renderedPages.has(pageNum)) applyAnnotationsToPage(el, pageNum);
    if (konvaStages.has(pageNum)) renderKonvaAnnotations(pageNum);
  }
}

watch(() => props.annotations, () => redrawAllAnnotations(), { deep: true });

function hideSelectionMenu() {
  if (selectionMenu.value.visible) selectionMenu.value = { visible: false, x: 0, y: 0, activeColor: '' };
  selectionDraft = null;
}

watch(activeAnnotationTool, (tool) => {
  hideSelectionMenu();
  cancelKonvaDraft();
  textDraft?.commit();
  suppressSelectionAfterPointer = false;
  window.getSelection()?.removeAllRanges();

  // Persistierte Textnotizen bleiben jederzeit verschiebbar, solange das
  // Text-Werkzeug aktiv ist — ohne die Stage neu zu rendern (sonst ginge ein
  // laufender Drag verloren).
  const isText = tool === 'text';
  for (const stageEntry of konvaStages.values()) {
    for (const label of stageEntry.layer.find('Label')) {
      label.draggable(isText);
    }
  }
});

function eraseAnnotationFromEvent(event) {
  // event.target ist während des Radierer-Werkzeugs meist das (unsichtbare,
  // aber pointer-events:auto) Konva-Canvas, das über der ganzen Seite liegt —
  // .closest() auf event.target würde die darunterliegende DOM-Markierung nie
  // finden. elementsFromPoint prüft den ganzen Stapel an dieser Stelle.
  const stack = document.elementsFromPoint(event.clientX, event.clientY);
  const rectEl = stack.find((el) => el.classList?.contains('pm-annot-rect'));
  const annotationId = rectEl?.dataset?.annotId;
  if (!annotationId) return false;
  emit('delete-annotation', annotationId);
  return true;
}

/**
 * Rechteck/Stift/Text werden über die Konva-Stage der jeweiligen Seite
 * gezeichnet (siehe attachStageDraftHandlers) — hier nur noch der Radierer
 * für die DOM-basierten Kinds (Highlight/Unterstreichung/Verknüpfung/Notiz)
 * sowie das Unterdrücken der Textauswahl während ein Werkzeug aktiv ist.
 */
function onPagesPointerDown(event) {
  const tool = activeAnnotationTool.value;
  if (!tool) return;

  if (tool === 'eraser') {
    if (!eraseAnnotationFromEvent(event)) return;
    event.preventDefault();
    event.stopPropagation();
    suppressSelectionAfterPointer = true;
    hideSelectionMenu();
    window.getSelection()?.removeAllRanges();
    return;
  }

  if (tool === 'rectangle' || tool === 'pen' || tool === 'text') {
    suppressSelectionAfterPointer = true;
    hideSelectionMenu();
    window.getSelection()?.removeAllRanges();
  }
}

function onPagesPointerMove(event) {
  onMagnifierPointerMove(event);
}

function onPagesPointerLeave() {
  hideMagnifier();
}

/** Liest die aktuelle Textauswahl und positioniert das Auswahl-Menü. */
function onPagesPointerUp(event) {
  if (suppressSelectionAfterPointer) {
    suppressSelectionAfterPointer = false;
    hideSelectionMenu();
    return;
  }
  if (!props.annotatable) return;
  if (activeAnnotationTool.value && activeAnnotationTool.value !== 'highlight') {
    hideSelectionMenu();
    return;
  }
  // Einen Tick warten, damit die Selection final steht.
  setTimeout(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) { hideSelectionMenu(); return; }
    const quote = sel.toString().trim();
    if (!quote) { hideSelectionMenu(); return; }

    const range = sel.getRangeAt(0);
    const startEl = range.startContainer.nodeType === 1
      ? range.startContainer
      : range.startContainer.parentElement;
    const pageEl = startEl?.closest?.('.pdf-preview__page');
    const pageNum = Number(pageEl?.dataset.page || 0);
    const innerEl = pageInnerRefs.get(pageNum);
    if (!innerEl) { hideSelectionMenu(); return; }

    const innerRect = innerEl.getBoundingClientRect();
    if (!innerRect.width || !innerRect.height) { hideSelectionMenu(); return; }

    const clamp = (v) => Math.min(1, Math.max(0, v));
    const visibleRects = [];
    for (const r of range.getClientRects()) {
      if (r.width < 1 || r.height < 1) continue;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      // Nur Rechtecke innerhalb DIESER Seite übernehmen.
      if (cx < innerRect.left || cx > innerRect.right || cy < innerRect.top || cy > innerRect.bottom) continue;
      visibleRects.push({
        x: clamp((r.left - innerRect.left) / innerRect.width),
        y: clamp((r.top  - innerRect.top)  / innerRect.height),
        w: clamp(r.width  / innerRect.width),
        h: clamp(r.height / innerRect.height),
      });
    }
    if (!visibleRects.length) { hideSelectionMenu(); return; }

    const rects = visibleRects.map((rect) => rectFromRotation(rect, pageRotation(pageNum)));
    const overlappingAnnotations = annotationsForSelection(pageNum, rects);
    selectionDraft = { page: pageNum, rects, quote, annotations: overlappingAnnotations };

    if (activeAnnotationTool.value === 'highlight') {
      toggleAnnotationColorFromSelection(DEFAULT_ANNOT_COLOR);
      return;
    }

    const rootRect = rootEl.value?.getBoundingClientRect();
    const first = range.getClientRects()[0];
    if (rootRect && first) {
      selectionMenu.value = {
        visible: true,
        x: first.left - rootRect.left + first.width / 2,
        y: first.top  - rootRect.top,
        activeColor: activeSelectionColor(overlappingAnnotations),
      };
    }
  }, 0);
}

function toggleAnnotationColorFromSelection(color) {
  if (!selectionDraft) return;
  const highlights = highlightAnnotationsForSelection();
  const nextColor = normalizedColor(color);
  const sameColorHighlights = highlights.filter((annot) => normalizedColor(annot.color) === nextColor);

  if (sameColorHighlights.length && sameColorHighlights.length === highlights.length) {
    for (const annot of sameColorHighlights) emit('delete-annotation', annot.id);
    window.getSelection()?.removeAllRanges();
    hideSelectionMenu();
    return;
  }

  if (highlights.length) {
    for (const annot of highlights) emit('update-annotation', annot.id, { color });
    window.getSelection()?.removeAllRanges();
    hideSelectionMenu();
    return;
  }

  emit('create-annotation', {
    page: selectionDraft.page,
    kind: 'highlight',
    color,
    rects: selectionDraft.rects,
    quote: selectionDraft.quote,
  });
  window.getSelection()?.removeAllRanges();
  hideSelectionMenu();
}

async function copySelection() {
  if (!selectionDraft) return;
  try { await navigator.clipboard?.writeText(selectionDraft.quote); } catch (_) { /* clipboard blockiert */ }
  window.getSelection()?.removeAllRanges();
  hideSelectionMenu();
}

function requestLinkFromSelection() {
  if (!selectionDraft) return;
  // Auswahl an den Parent geben; der öffnet den Ziel-Picker und legt danach die
  // Verknüpfung über das normale create-annotation an (kind: 'link').
  emit('request-link', {
    page: selectionDraft.page,
    rects: selectionDraft.rects,
    quote: selectionDraft.quote,
  });
  window.getSelection()?.removeAllRanges();
  hideSelectionMenu();
}

function requestCommentFromSelection() {
  if (!selectionDraft) return;
  emit('request-comment', {
    page: selectionDraft.page,
    rects: selectionDraft.rects,
    quote: selectionDraft.quote,
    color: COMMENT_ANNOTATION_COLOR,
  });
  window.getSelection()?.removeAllRanges();
  hideSelectionMenu();
}

// ─── Rendering ───────────────────────────────────────────────────────────────

async function renderPage(pageNum) {
  if (renderQueue.has(pageNum)) return;
  if (renderedPages.has(pageNum)) return;
  if (!pdfDoc) return;

  const epoch = loadEpoch;
  const generation = renderGeneration;
  renderQueue.add(pageNum);

  try {
    const page = await pdfDoc.getPage(pageNum);
    if (epoch !== loadEpoch || generation !== renderGeneration) return;

    const info = pageInfos.value[pageNum - 1];
    if (!info) return;

    const innerEl = pageInnerRefs.get(pageNum);
    if (!innerEl) return;

    const scale    = computeScale(info);
    const viewport = page.getViewport({ scale, rotation: normalizeRotation(page.rotate + pageRotation(pageNum)) });

    // HiDPI/Retina: Backing-Store in GERÄTEPIXELN rendern, Anzeige bleibt logisch
    // (Canvas-CSS = 100 % der logisch dimensionierten Seite). Ohne diesen Faktor
    // wird das Canvas auf Retina-Displays hochskaliert dargestellt → unscharf.
    // Ein Cap pro Dimension verhindert exzessive Canvas-Größen bei hohem Zoom.
    const MAX_CANVAS_DIM = 5000;
    let outputScale = window.devicePixelRatio || 1;
    const maxTargetDim = Math.max(viewport.width, viewport.height) * outputScale;
    if (maxTargetDim > MAX_CANVAS_DIM) {
      outputScale *= MAX_CANVAS_DIM / maxTargetDim;
    }

    // Canvas erstellen und rendern
    const canvas = document.createElement('canvas');
    const ctx    = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;

    canvas.width  = Math.floor(viewport.width  * outputScale);
    canvas.height = Math.floor(viewport.height * outputScale);

    const renderContext = { canvasContext: ctx, viewport, background: 'rgb(255,255,255)' };
    if (outputScale !== 1) {
      renderContext.transform = [outputScale, 0, 0, outputScale, 0, 0];
    }
    await page.render(renderContext).promise;
    if (epoch !== loadEpoch || generation !== renderGeneration) return;

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
    if (epoch !== loadEpoch || generation !== renderGeneration) return;

    // LRU-Eviction: älteste Seite entfernen wenn Cache voll
    if (renderedPages.size >= MAX_CACHED_PAGES) {
      const oldest = renderedPages.values().next().value;
      renderedPages.delete(oldest);
      destroyKonvaStage(oldest);
      const oldEl = pageInnerRefs.get(oldest);
      if (oldEl) oldEl.innerHTML = '';
    }

    // --total-scale-factor für TextLayer-Positionierung
    innerEl.style.setProperty('--total-scale-factor', String(scale));

    // Canvas + TextLayer in DOM einhängen
    destroyKonvaStage(pageNum);
    innerEl.innerHTML = '';
    innerEl.appendChild(canvas);
    innerEl.appendChild(textLayerDiv);

    // Highlights anwenden (nach DOM-Einhängen, damit normalize() korrekt arbeitet)
    applyHighlights(textLayerDiv);
    rebuildHighlightTargets();
    applyAnnotationsToPage(innerEl, pageNum);
    ensureKonvaStage(pageNum, innerEl, viewport.width, viewport.height);
    renderKonvaAnnotations(pageNum);

    renderedPages.add(pageNum);
    if (!firstPageReady.value) firstPageReady.value = true;
    page.cleanup();
  } catch (_err) {
    // Einzelseite konnte nicht gerendert werden – kein Fatal-Error
  } finally {
    renderQueue.delete(pageNum);
  }
}

function rotateActivePage(delta) {
  const pageNum = currentPage.value;
  if (!pageNum || !pageInfos.value[pageNum - 1]) return;

  pageRotations.value = {
    ...pageRotations.value,
    [pageNum]: normalizeRotation(pageRotation(pageNum) + delta),
  };

  renderGeneration++;
  renderQueue.delete(pageNum);
  renderedPages.delete(pageNum);
  hideMagnifier();
  hideSelectionMenu();

  destroyKonvaStage(pageNum);
  const innerEl = pageInnerRefs.get(pageNum);
  if (innerEl) innerEl.innerHTML = '';

  nextTick(() => {
    scrollToPage(pageNum);
    renderPage(pageNum);
  });
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
  hideSelectionMenu();
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
  const anchor = pendingZoomAnchor;
  pendingZoomAnchor = null;
  // Ein laufender pdf.js-Render passt nicht mehr zum aktuellen Zoom. Nicht sofort
  // neu rendern: Trackpads liefern viele kleine Deltas und würden sonst stottern.
  renderGeneration++;
  hideMagnifier();
  hideSelectionMenu();
  await nextTick();
  restoreZoomAnchor(anchor);
  scheduleZoomRender();
});

// ─── PDF Laden ───────────────────────────────────────────────────────────────

async function loadPdf(src) {
  const epoch = ++loadEpoch;

  teardownObservers();
  hideMagnifier();
  hideSelectionMenu();
  if (zoomRenderTimer) {
    window.clearTimeout(zoomRenderTimer);
    zoomRenderTimer = 0;
  }
  lastRenderWidth = 0;
  renderGeneration++;
  renderedPages.clear();
  renderQueue.clear();
  for (const pageNum of [...konvaStages.keys()]) destroyKonvaStage(pageNum);
  pageInnerRefs.clear();
  pageInfos.value   = [];
  pageRotations.value = {};
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

function goToPage(pageNum) {
  const total = pageInfos.value.length;
  if (!total) return;
  scrollToPage(Math.min(Math.max(1, pageNum), total));
}

const pageCount = computed(() => pageInfos.value.length);

/**
 * Rendert eine Seite klein in das übergebene Canvas (für die Miniatur-Leiste des
 * Lesemodus). Nutzt das bereits geladene pdfDoc – KEIN zweiter Netzwerk-Ladevorgang.
 * Fehler werden geschluckt (Platzhalter bleibt stehen).
 */
async function renderThumbnail(pageNum, canvas, cssWidth = 116) {
  if (!pdfDoc || !canvas) return;
  try {
    const page = await pdfDoc.getPage(pageNum);
    const base = page.getViewport({ scale: 1 });
    const scale = cssWidth / base.width;
    const vp = page.getViewport({ scale });
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = Math.floor(vp.width  * dpr);
    canvas.height = Math.floor(vp.height * dpr);
    canvas.style.width  = `${Math.floor(vp.width)}px`;
    canvas.style.height = `${Math.floor(vp.height)}px`;
    const ctx = canvas.getContext('2d', { alpha: false });
    if (!ctx) return;
    const renderContext = { canvasContext: ctx, viewport: vp, background: 'rgb(255,255,255)' };
    if (dpr !== 1) renderContext.transform = [dpr, 0, 0, dpr, 0, 0];
    await page.render(renderContext).promise;
    page.cleanup();
  } catch (_) {
    /* Miniatur konnte nicht gerendert werden – unkritisch */
  }
}

defineExpose({ goToPage, currentPage, pageCount, renderThumbnail });

// ─── Tastenkürzel ─────────────────────────────────────────────────────────────
// Aktiv, sobald der Viewer (oder ein Kind) den Fokus hat – stört also keine
// Eingaben außerhalb der Vorschau. Hoch/Runter bleiben dem nativen Scrollen
// überlassen; Links/Rechts springen seitenweise.

function onKeydown(event) {
  const target = event.target;
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return;
  }

  switch (event.key) {
    case '+':
    case '=':
      zoomIn();
      event.preventDefault();
      break;
    case '-':
    case '_':
      zoomOut();
      event.preventDefault();
      break;
    case 'ArrowRight':
      goToPage(currentPage.value + 1);
      event.preventDefault();
      break;
    case 'ArrowLeft':
      goToPage(currentPage.value - 1);
      event.preventDefault();
      break;
    case 'n':
      if (props.highlightText) { navigateHighlight(1); event.preventDefault(); }
      break;
    case 'N':
      if (props.highlightText) { navigateHighlight(-1); event.preventDefault(); }
      break;
    case 'Enter':
      if (props.highlightText) { navigateHighlight(event.shiftKey ? -1 : 1); event.preventDefault(); }
      break;
    case 'f':
    case 'F':
      if (props.enableReader) { emit('open-reader'); event.preventDefault(); }
      break;
    default:
      break;
  }
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
  // Toleranz: Sub-Pixel-/1px-Schwankungen (z. B. durch eine laufende Layout-
  // Animation der Nachbarspalten) sollen kein Neu-Rendern auslösen.
  const width = containerWidth();
  if (Math.abs(width - lastRenderWidth) <= 2) return;
  lastRenderWidth = width;

  if (resizeRaf) cancelAnimationFrame(resizeRaf);
  resizeRaf = requestAnimationFrame(() => {
    resizeRaf = 0;
    renderGeneration++;
    renderedPages.clear();
    renderQueue.clear();
    highlightTargets = [];
    highlightCount.value = 0;
    activeHighlightIndex.value = -1;
    setupObservers();
  });
}

watch(pagesEl, (el, oldEl) => {
  resizeObserver?.disconnect();
  detachGestureZoomListeners(oldEl);
  if (!el) return;
  resizeObserver = new ResizeObserver(onResize);
  resizeObserver.observe(el);
  attachGestureZoomListeners(el);
});

// ─── Cleanup ─────────────────────────────────────────────────────────────────

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKeydownCapture, true);
  for (const pageNum of [...konvaStages.keys()]) destroyKonvaStage(pageNum);
  loadEpoch++;
  teardownObservers();
  resizeObserver?.disconnect();
  detachGestureZoomListeners(pagesEl.value);
  if (resizeRaf)      cancelAnimationFrame(resizeRaf);
  if (scrollRafId)    cancelAnimationFrame(scrollRafId);
  if (highlightFlashTimer) window.clearTimeout(highlightFlashTimer);
  if (zoomRenderTimer) window.clearTimeout(zoomRenderTimer);
  if (activeLoadTask) try { activeLoadTask.destroy(); } catch (_) {}
  if (pdfDoc)         try { pdfDoc.destroy(); }         catch (_) {}
});
</script>

<style scoped>
.pdf-preview {
  --pdf-toolbar-bg: rgb(15 23 42 / 0.72);
  --pdf-toolbar-border: rgb(255 255 255 / 0.1);
  --pdf-toolbar-shadow: 0 8px 22px rgb(0 0 0 / 0.24);
  --pdf-toolbar-text: rgb(226 232 240 / 0.85);
  --pdf-toolbar-text-muted: rgb(226 232 240 / 0.68);
  --pdf-toolbar-icon: rgb(226 232 240 / 0.72);
  --pdf-toolbar-hover-bg: rgb(255 255 255 / 0.1);
  --pdf-toolbar-stepper-bg: rgb(255 255 255 / 0.07);
  --pdf-toolbar-divider: rgb(255 255 255 / 0.12);
  --pdf-toolbar-group-gap: 8px;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-viewer-surface, rgb(var(--v-theme-surface)));
}

.pdf-preview--document-ready {
  background: var(--pm-pdf-stage-bg, rgb(var(--v-theme-surface)));
}

:global(.v-theme--light) .pdf-preview,
:global(.papermind-app.v-theme--light) .pdf-preview {
  --pdf-toolbar-bg: rgb(255 255 255 / 0.94);
  --pdf-toolbar-border: rgb(203 213 225 / 0.92);
  --pdf-toolbar-shadow:
    0 14px 34px rgb(15 23 42 / 0.12),
    0 2px 8px rgb(15 23 42 / 0.08);
  --pdf-toolbar-text: rgb(31 41 55 / 0.88);
  --pdf-toolbar-text-muted: rgb(75 85 99 / 0.72);
  --pdf-toolbar-icon: rgb(71 85 105 / 0.76);
  --pdf-toolbar-hover-bg: rgb(15 23 42 / 0.07);
  --pdf-toolbar-stepper-bg: rgb(241 245 249 / 0.96);
  --pdf-toolbar-divider: rgb(148 163 184 / 0.24);
}

/* ── Toolbar ─────────────────────────────────────────────────────────────── */
.pdf-preview__toolbar {
  position: absolute;
  top: 12px;
  left: 50%;
  right: auto;
  transform: translateX(-50%);
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: 0;
  max-width: calc(100% - 24px);
  min-height: 34px;
  gap: var(--pdf-toolbar-group-gap);
  padding: 4px 8px;
  border: 1px solid var(--pdf-toolbar-border);
  border-radius: 999px;
  background: var(--pdf-toolbar-bg);
  box-shadow: var(--pdf-toolbar-shadow);
  backdrop-filter: blur(12px) saturate(1.08);
  -webkit-backdrop-filter: blur(12px) saturate(1.08);
  box-sizing: border-box;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 160ms ease,
    background 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.pdf-preview__viewer:has(.pdf-preview__page:hover) .pdf-preview__toolbar,
.pdf-preview__toolbar:hover,
.pdf-preview__toolbar:focus-within {
  opacity: 1;
  pointer-events: auto;
}

@media (prefers-reduced-motion: reduce) {
  .pdf-preview__toolbar,
  .pdf-preview-match-enter-active,
  .pdf-preview-match-leave-active {
    transition: none;
  }
}

.pdf-preview__left-controls {
  position: static;
  display: flex;
  align-items: center;
  gap: var(--pdf-toolbar-group-gap);
}

.pdf-preview__page-info {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 3.4rem;
  height: 26px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--pdf-toolbar-stepper-bg);
  color: var(--pdf-toolbar-text);
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.pdf-preview__match-controls {
  display: inline-flex;
  align-items: center;
  gap: 0;
  flex: 0 0 auto;
  overflow: hidden;
  white-space: nowrap;
  padding: 1px;
  border-radius: 999px;
  background: var(--pdf-toolbar-stepper-bg);
}

.pdf-preview-match-enter-active,
.pdf-preview-match-leave-active {
  max-width: 220px;
  opacity: 1;
  transition:
    max-width 190ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 140ms ease,
    transform 190ms cubic-bezier(0.22, 1, 0.36, 1);
}

.pdf-preview-match-enter-from,
.pdf-preview-match-leave-to {
  max-width: 0;
  opacity: 0;
  transform: scaleX(0.92);
}

.pdf-preview-match-enter-to,
.pdf-preview-match-leave-from {
  max-width: 220px;
  opacity: 1;
  transform: scaleX(1);
}

.pdf-preview__match-nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pdf-toolbar-icon);
  cursor: pointer;
  line-height: 1;
  transition: background 140ms ease, color 140ms ease, transform 120ms ease, opacity 140ms ease;
}

.pdf-preview__match-nav-btn:hover:not(:disabled) {
  background: var(--pdf-toolbar-hover-bg);
  color: var(--pdf-toolbar-text);
}

.pdf-preview__match-nav-btn:active:not(:disabled) {
  transform: scale(0.9);
}

.pdf-preview__match-nav-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.pdf-preview__match-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 5.2rem;
  height: 26px;
  padding: 0 6px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pdf-toolbar-text);
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
  flex: 0 0 auto;
  text-align: center;
}

.pdf-preview__match-badge--zero {
  background: transparent;
  color: var(--pdf-toolbar-text-muted);
  font-weight: 400;
}

.pdf-preview__rotate-controls {
  display: inline-flex;
  align-items: center;
  gap: 0;
  padding: 1px;
  border-radius: 999px;
  background: var(--pdf-toolbar-stepper-bg);
}

.pdf-preview__rotate-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pdf-toolbar-icon);
  cursor: pointer;
  line-height: 1;
  transition: background 140ms ease, color 140ms ease, transform 120ms ease, opacity 140ms ease;
}

.pdf-preview__rotate-btn:hover:not(:disabled) {
  background: var(--pdf-toolbar-hover-bg);
  color: var(--pdf-toolbar-text);
}

.pdf-preview__rotate-btn:active:not(:disabled) {
  transform: scale(0.9);
}

.pdf-preview__rotate-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

.pdf-preview__zoom-controls {
  position: static;
  display: flex;
  align-items: center;
  gap: var(--pdf-toolbar-group-gap);
}

/* Zoom: zusammenhängendes, weiches Pill-Steuerelement (−  100 %  +). */
.pdf-preview__zoom-stepper {
  display: inline-flex;
  align-items: center;
  gap: 0;
  padding: 1px;
  border-radius: 999px;
  background: var(--pdf-toolbar-stepper-bg);
}

.pdf-preview__zoom-seg {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pdf-toolbar-icon);
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease, transform 120ms ease, opacity 140ms ease;
}

.pdf-preview__zoom-seg:hover:not(:disabled) {
  background: var(--pdf-toolbar-hover-bg);
  color: var(--pdf-toolbar-text);
}

.pdf-preview__zoom-seg:active:not(:disabled) {
  transform: scale(0.9);
}

.pdf-preview__zoom-seg:disabled {
  opacity: 0.28;
  cursor: default;
}

.pdf-preview__zoom-value {
  min-width: 2.7rem;
  height: 26px;
  padding: 0 2px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pdf-toolbar-text);
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease;
}

.pdf-preview__zoom-value:hover {
  background: var(--pdf-toolbar-hover-bg);
  color: var(--pdf-toolbar-text);
}

.pdf-preview__zoom-value--default {
  color: var(--pdf-toolbar-text-muted);
}

/* ── Lupe-Toggle ─────────────────────────────────────────────────────────── */
.pdf-preview__tool-btn {
  width: 28px;
  height: 26px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  color: var(--pdf-toolbar-icon);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 140ms ease, color 140ms ease, transform 120ms ease;
}

.pdf-preview__tool-btn:active:not(:disabled) {
  transform: scale(0.92);
}

.pdf-preview__tool-btn:hover:not(:disabled):not(.pdf-preview__tool-btn--active) {
  background: var(--pdf-toolbar-hover-bg);
  color: var(--pdf-toolbar-text);
}

.pdf-preview__tool-btn:disabled {
  opacity: 0.3;
  cursor: default;
}

.pdf-preview__tool-btn--active {
  background: rgb(var(--v-theme-primary));
  border-color: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  box-shadow:
    0 0 0 3px rgb(var(--v-theme-primary) / 0.28),
    0 2px 8px rgb(var(--v-theme-primary) / 0.4);
}

.pdf-preview__tool-btn--active:hover {
  background: rgb(var(--v-theme-primary));
  filter: brightness(1.08);
}

.pdf-preview__tool-divider {
  width: 1px;
  height: 16px;
  background: var(--pdf-toolbar-divider);
  margin: 0 2px;
}

/* ── Lupe ──────────────────────────────────────────────────────────────────── */
.pdf-preview__pages--magnify {
  cursor: crosshair;
}

.pdf-preview__pages--magnify :deep(.textLayer) {
  pointer-events: none;
}

.pdf-preview__loupe {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 3;
  pointer-events: none;
  border: 2px solid rgb(var(--v-theme-surface) / 0.96);
  border-radius: 10px;
  background: #fff;
  box-shadow:
    0 10px 28px rgb(0 0 0 / 0.28),
    inset 0 0 0 1px rgb(0 0 0 / 0.12);
  will-change: transform;
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
  padding: 0 14px 14px;
}

.pdf-preview__pages:focus {
  outline: none;
}

.pdf-preview__pages:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary) / 0.5);
  outline-offset: -2px;
}

.pdf-preview--tool-rectangle .pdf-preview__pages {
  cursor: crosshair;
}

.pdf-preview--tool-pen .pdf-preview__pages {
  cursor: crosshair;
}

.pdf-preview--tool-text .pdf-preview__pages {
  cursor: text;
}

.pdf-preview--tool-eraser .pdf-preview__pages {
  cursor: default;
}

/* ── Einzelne Seite ─────────────────────────────────────────────────────── */
.pdf-preview__page {
  flex: 0 0 auto;
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  background: var(--pm-pdf-page-bg, #fff);
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
  background: var(--pm-pdf-page-bg, rgb(var(--v-theme-on-surface) / 0.05));
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
  z-index: 3;
}

.pdf-preview--tool-text .pdf-preview__page-inner :deep(.textLayer),
.pdf-preview--tool-pen .pdf-preview__page-inner :deep(.textLayer),
.pdf-preview--tool-rectangle .pdf-preview__page-inner :deep(.textLayer),
.pdf-preview--tool-eraser .pdf-preview__page-inner :deep(.textLayer) {
  pointer-events: none;
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

/* ── Markierungsebene (Annotations) ──────────────────────────────────────── */
/* DOM-Ebene für Highlight/Unterstreichung/Verknüpfung/Notiz: liegt zwischen
   Canvas und TextLayer, pointer-events: none, damit Textauswahl/Neu-Markieren
   durch die Highlights hindurch funktioniert. Rechteck/Stift/Text laufen
   separat über die Konva-Ebene (siehe .pm-konva-layer weiter unten). */
.pdf-preview__page-inner :deep(.pm-annot-layer) {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

.pdf-preview--tool-eraser .pdf-preview__page-inner :deep(.pm-annot-layer) {
  pointer-events: auto;
  z-index: 4;
}

.pdf-preview__page-inner :deep(.pm-annot-rect) {
  position: absolute;
  border-radius: 2px;
  opacity: 0.4;
  mix-blend-mode: multiply;
  animation: pm-annot-in 180ms ease;
}

.pdf-preview--tool-eraser .pdf-preview__page-inner :deep(.pm-annot-rect) {
  pointer-events: auto;
  cursor: pointer;
}

.pdf-preview--tool-eraser .pdf-preview__page-inner :deep(.pm-annot-rect:hover) {
  opacity: 0.72;
  outline: 2px solid rgb(var(--v-theme-error) / 0.78);
  outline-offset: 1px;
}

/* from-only Keyframe: animiert von opacity 0 zur jeweiligen Eigen-Opazität. */
@keyframes pm-annot-in {
  from { opacity: 0; }
}

.pdf-preview__page-inner :deep(.pm-annot-rect--underline) {
  opacity: 0.95;
  border-radius: 0;
  border-bottom: 2px solid currentColor;
  background: transparent !important;
}

/* Verknüpfungen: getönt wie ein Highlight, zusätzlich gestrichelte Linkfarbe. */
.pdf-preview__page-inner :deep(.pm-annot-rect--link) {
  border-bottom: 2px dashed rgba(24, 95, 165, 0.9);
}

/* ── Konva-Ebene: Rechteck/Stift/Text (Zeichnen + persistierte Anzeige) ───── */
/* Liegt ÜBER dem TextLayer (anders als .pm-annot-layer) — das sind eigene
   Zeichnungen, keine Text-Overlays. pointer-events nur aktiv, während eines
   der zugehörigen Werkzeuge gewählt ist, sonst bleibt der TextLayer darunter
   für Auswahl/Highlight erreichbar. */
.pdf-preview__page-inner :deep(.pm-konva-layer) {
  position: absolute;
  inset: 0;
  z-index: 4;
  pointer-events: none;
}

.pdf-preview--tool-rectangle .pdf-preview__page-inner :deep(.pm-konva-layer),
.pdf-preview--tool-pen .pdf-preview__page-inner :deep(.pm-konva-layer),
.pdf-preview--tool-text .pdf-preview__page-inner :deep(.pm-konva-layer),
.pdf-preview--tool-eraser .pdf-preview__page-inner :deep(.pm-konva-layer) {
  pointer-events: auto;
}

/* Echte <textarea> zum Tippen, liegt über der Konva-Box (die Rahmen/Hintergrund
   liefert); leicht eingerückt, damit die Transformer-Anfasser am Rand der
   Konva-Box klickbar bleiben statt von der Textarea verdeckt zu werden. */
.pdf-preview__page-inner :deep(.pm-text-draft) {
  position: absolute;
  padding: 0;
  border: none;
  outline: none;
  resize: none;
  pointer-events: auto;
  background: transparent;
  color: rgb(15 23 42);
  font: 500 14px/1.3 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  z-index: 5;
}

/* ── Auswahl-Menü ─────────────────────────────────────────────────────────── */
.pm-sel-menu {
  --pm-sel-menu-bg: rgb(255 255 255 / 0.92);
  --pm-sel-menu-border: rgb(15 23 42 / 0.1);
  --pm-sel-menu-shadow: 0 10px 24px rgb(15 23 42 / 0.16);
  --pm-sel-menu-icon: rgb(15 23 42 / 0.62);
  --pm-sel-menu-icon-hover: rgb(15 23 42 / 0.86);
  --pm-sel-menu-hover-bg: rgb(15 23 42 / 0.08);
  --pm-sel-menu-divider: rgb(15 23 42 / 0.12);
  --pm-sel-menu-swatch-border: rgb(15 23 42 / 0.18);
  --pm-sel-menu-swatch-active-ring: rgb(15 23 42 / 0.48);
  position: absolute;
  z-index: 5;
  transform: translate(-50%, calc(-100% - 8px));
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 7px;
  border-radius: 10px;
  background: var(--pm-sel-menu-bg);
  border: 1px solid var(--pm-sel-menu-border);
  box-shadow: var(--pm-sel-menu-shadow);
  backdrop-filter: blur(12px) saturate(1.08);
  -webkit-backdrop-filter: blur(12px) saturate(1.08);
  animation: pm-sel-pop 130ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

:global(.v-theme--dark) .pm-sel-menu {
  --pm-sel-menu-bg: rgb(15 23 42 / 0.86);
  --pm-sel-menu-border: rgb(255 255 255 / 0.1);
  --pm-sel-menu-shadow: 0 10px 24px rgb(0 0 0 / 0.28);
  --pm-sel-menu-icon: rgb(226 232 240 / 0.68);
  --pm-sel-menu-icon-hover: rgb(226 232 240 / 0.92);
  --pm-sel-menu-hover-bg: rgb(255 255 255 / 0.1);
  --pm-sel-menu-divider: rgb(255 255 255 / 0.14);
  --pm-sel-menu-swatch-border: rgb(255 255 255 / 0.24);
  --pm-sel-menu-swatch-active-ring: rgb(226 232 240 / 0.72);
}

@keyframes pm-sel-pop {
  from { opacity: 0; transform: translate(-50%, calc(-100% - 2px)) scale(0.96); }
  to   { opacity: 1; transform: translate(-50%, calc(-100% - 8px)) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .pdf-preview__page-inner :deep(.pm-annot-rect),
  .pm-sel-menu {
    animation: none;
  }
}

.pm-sel-menu__color {
  position: relative;
  width: 18px;
  height: 18px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--pm-sel-menu-swatch-border);
  cursor: pointer;
  transition: box-shadow 120ms ease, transform 120ms ease;
}

.pm-sel-menu__color:hover {
  transform: scale(1.15);
}

.pm-sel-menu__color::after {
  content: '';
  position: absolute;
  inset: 2px;
  border: 2px solid transparent;
  border-radius: inherit;
  pointer-events: none;
  transition: border-color 120ms ease;
}

.pm-sel-menu__color--active {
  border-color: var(--pm-sel-menu-swatch-active-ring);
}

.pm-sel-menu__color--active::after {
  border-color: var(--pm-sel-menu-swatch-active-ring);
}

.pm-sel-menu__divider {
  width: 1px;
  height: 18px;
  background: var(--pm-sel-menu-divider);
  margin: 0 2px;
}

.pm-sel-menu__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-sel-menu-icon);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
}

.pm-sel-menu__btn:hover {
  background: var(--pm-sel-menu-hover-bg);
  color: var(--pm-sel-menu-icon-hover);
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

/* Fehlerzustand nutzt die Standard-Placeholder-Komponente (PmEmptyState). */
.pdf-preview__placeholder {
  flex: 1;
  min-height: 0;
  display: flex;
}
</style>

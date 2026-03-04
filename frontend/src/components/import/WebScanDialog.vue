<template>
  <BaseDialog
    v-model="isOpen"
    :persistent="isBusy"
    max-width="1000"
    card-class="web-scan-dialog"
    body-class="web-scan-dialog__body"
    :title="dialogTitle"
    :header-subtitle="dialogSubtitle"
    :show-secondary="false"
    description=""
    @close="handleDialogClose"
  >
    <div class="web-scan" :class="`is-${step}`">
      <section v-if="step === 'camera'" class="web-scan__camera">
        <div class="web-scan__camera-shell">
          <video
            ref="videoRef"
            class="web-scan__video"
            autoplay
            playsinline
            muted
            :class="{ 'is-hidden': cameraState !== 'ready' }"
          />
          <canvas ref="overlayCanvasRef" class="web-scan__overlay-canvas" aria-hidden="true" />

          <div v-if="cameraState !== 'ready'" class="web-scan__camera-fallback">
            <v-icon size="44">mdi-camera-off-outline</v-icon>
            <p class="web-scan__camera-fallback-title">Kamera nicht verfügbar</p>
            <p class="web-scan__camera-fallback-text">{{ cameraFallbackHint }}</p>
            <v-btn variant="tonal" color="primary" prepend-icon="mdi-file-image-outline" @click="openFallbackPicker">
              Datei auswählen
            </v-btn>
          </div>

          <div v-if="cameraState === 'ready'" class="web-scan__hud web-scan__hud--left">
            <span class="web-scan__state-chip" :class="`is-${scanState}`">{{ stateLabel }}</span>
            <span v-if="showDebugOverlay" class="web-scan__metric-chip">
              {{ Math.round(latestConfidence * 100) }}% · {{ workerDetectionEngine === 'opencv' ? 'CV' : 'JS' }}
            </span>
          </div>

          <div v-if="cameraState === 'ready' && workerHintText" class="web-scan__init-hint">
            {{ workerHintText }}
          </div>

          <div v-if="cameraState === 'ready' && showDebugOverlay" class="web-scan__debug-panel">
            <div>state: {{ scanState }}</div>
            <div>conf: {{ latestConfidence.toFixed(2) }} · area: {{ latestAreaRatio.toFixed(2) }}</div>
            <div>jitter: {{ latestJitter.toFixed(4) }} · areaΔ: {{ latestAreaDelta.toFixed(4) }}</div>
            <div>edge: {{ latestEdgeStrength.toFixed(2) }} · angle: {{ latestAnglesScore.toFixed(2) }}</div>
          </div>
        </div>

        <div class="web-scan__camera-controls">
          <label class="web-scan__auto-toggle">
            <input v-model="autoScanEnabled" type="checkbox" />
            <span>Auto-Scan</span>
          </label>
          <v-btn
            color="primary"
            variant="flat"
            size="large"
            :disabled="cameraState !== 'ready' || isBusy"
            :loading="isCapturing"
            prepend-icon="mdi-camera"
            @click="captureCurrentFrame('manual')"
          >
            Aufnehmen
          </v-btn>
          <v-btn variant="text" :disabled="isBusy" @click="isOpen = false">Abbrechen</v-btn>
        </div>
      </section>

      <section v-else-if="step === 'review'" class="web-scan__review">
        <div class="web-scan__edit-stage">
          <div class="web-scan__image-wrap">
            <img
              v-if="capturedImageUrl"
              ref="editImageRef"
              class="web-scan__edit-image"
              :src="capturedImageUrl"
              :style="editPreviewStyle"
              alt="Scan-Vorschau"
            />

            <svg class="web-scan__overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <polygon :points="cropPolygon" class="web-scan__overlay-fill" />
              <polyline :points="cropPolyline" class="web-scan__overlay-line" />
            </svg>

            <button
              v-for="(point, index) in cropPoints"
              :key="`handle-${index}`"
              class="web-scan__handle"
              type="button"
              :style="handleStyle(point)"
              :aria-label="`Ecke ${index + 1}`"
              @pointerdown="onHandlePointerDown($event, index)"
            />
          </div>
        </div>

        <div class="web-scan__edit-controls">
          <div class="web-scan__filters" role="tablist" aria-label="Filter">
            <button
              v-for="option in FILTER_OPTIONS"
              :key="option.value"
              type="button"
              class="web-scan__filter-btn"
              :class="{ 'is-active': filterMode === option.value }"
              @click="filterMode = option.value"
            >
              {{ option.label }}
            </button>
          </div>

          <div class="web-scan__edit-actions">
            <v-btn variant="text" :disabled="isBusy" @click="retakeCapture">Neu aufnehmen</v-btn>
            <v-btn variant="text" :disabled="isBusy" @click="rotateOutput">90° drehen ({{ rotateLabel }})</v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :loading="isApplyingEdit"
              :disabled="isBusy"
              @click="addCurrentCaptureAsPage"
            >
              Weiter
            </v-btn>
          </div>
        </div>

        <p v-if="isDetecting" class="web-scan__subtle">Erkenne Dokumentkanten…</p>
      </section>

      <section v-else class="web-scan__pages">
        <div class="web-scan__pages-header">
          <div>
            <h3>Seiten</h3>
            <p>{{ pages.length }} Seite{{ pages.length === 1 ? '' : 'n' }}</p>
          </div>
          <v-btn variant="tonal" color="primary" prepend-icon="mdi-plus" @click="goToCameraForNextPage">
            Seite hinzufügen
          </v-btn>
        </div>

        <div class="web-scan__page-list">
          <div
            v-for="(page, index) in pages"
            :key="page.id"
            class="web-scan__page-row"
            draggable="true"
            @dragstart="onPageDragStart(index)"
            @dragover.prevent
            @drop.prevent="onPageDrop(index)"
          >
            <div class="web-scan__page-index">{{ index + 1 }}</div>
            <img class="web-scan__page-thumb" :src="page.previewUrl" :alt="`Seite ${index + 1}`" />
            <div class="web-scan__page-meta">
              <div class="web-scan__page-title">Seite {{ index + 1 }}</div>
              <div class="web-scan__page-subline">{{ filterLabel(page.filter) }} · {{ rotationLabel(page.rotationTurns) }}</div>
            </div>
            <v-btn icon="mdi-delete-outline" variant="text" size="small" aria-label="Seite löschen" @click="removePage(index)" />
          </div>
        </div>

        <div class="web-scan__pages-actions">
          <v-btn variant="text" :disabled="isBusy" @click="isOpen = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="isExporting"
            :disabled="pages.length === 0 || isBusy"
            @click="exportPdfAndFinish"
          >
            Fertig
          </v-btn>
        </div>
      </section>
    </div>

    <input
      ref="fallbackInputRef"
      class="d-none"
      type="file"
      accept="image/*,application/pdf"
      capture="environment"
      @change="onFallbackFileChange"
    />
  </BaseDialog>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import BaseDialog from '../BaseDialog.vue';
import { mapApiError, useNotifications } from '../../stores/notifications';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  outputMode: { type: String, default: 'pdf' }
});

const emit = defineEmits(['update:modelValue', 'pdf-ready', 'files-ready']);

const FILTER_OPTIONS = Object.freeze([
  { value: 'original', label: 'Original' },
  { value: 'gray', label: 'Grau' },
  { value: 'document', label: 'Dokument' }
]);

const LIVE_CONFIG = Object.freeze({
  cvFps: 10,
  autoShutterDelayMs: 800,
  minConfidenceTracking: 0.55,
  minConfidenceLocked: 0.78,
  minConfidenceCountdown: 0.72,
  jitterThreshold: 0.015,
  areaChangeThreshold: 0.06,
  stabilitySamples: 8,
  jumpSnapThreshold: 0.08,
  pointMargin: 0.02,
  downscaleLongEdge: 640,
  maxCaptureEdge: 2200
});

const DEFAULT_DETECTION_ENGINE = resolveDetectionEngineFlag();
const OPENCV_SCRIPT_URL = resolveOpenCvUrlFlag();
const WEBSCAN_DEBUG = String(import.meta.env.VITE_WEBSCAN_DEBUG || '')
  .trim()
  .toLowerCase() === 'true';

const { notify } = useNotifications();

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const emitsFiles = computed(() => String(props.outputMode || '').trim().toLowerCase() === 'files');

const step = ref('camera');
const videoRef = ref(null);
const overlayCanvasRef = ref(null);
const editImageRef = ref(null);
const fallbackInputRef = ref(null);

const cameraState = ref('idle');
const workerState = ref('initializing');
const requestedDetectionEngine = ref(DEFAULT_DETECTION_ENGINE);
const workerDetectionEngine = ref('heuristic');
const workerProcessingAvailable = ref(false);
const scanState = ref('searching');
const autoScanEnabled = ref(true);
const capturedImageUrl = ref('');
const capturedBlob = ref(null);
const cropPoints = ref(createDefaultQuad());
const filterMode = ref('document');
const rotationTurns = ref(0);
const pages = ref([]);

const isCapturing = ref(false);
const isDetecting = ref(false);
const isApplyingEdit = ref(false);
const isExporting = ref(false);

const latestConfidence = ref(0);
const latestAreaRatio = ref(0);
const latestJitter = ref(0);
const latestAreaDelta = ref(0);
const latestEdgeStrength = ref(0);
const latestAnglesScore = ref(0);
const latestBbox = ref(null);
const latestRawQuad = ref(null);
const smoothedQuad = ref(null);
const stabilitySamples = ref([]);
const lockStartedAt = ref(0);
const nowTs = ref(0);

const activeHandleIndex = ref(-1);
const activePointerId = ref(-1);
const draggedPageIndex = ref(-1);

const isBusy = computed(() => isCapturing.value || isDetecting.value || isApplyingEdit.value || isExporting.value);
const dialogTitle = computed(() => {
  if (step.value === 'review') {
    return 'Crop & Enhance';
  }
  if (step.value === 'pages') {
    return 'Scan-Seiten';
  }
  return 'Dokument scannen';
});

const dialogSubtitle = computed(() => {
  if (step.value === 'camera') {
    return 'Live-Rahmen, Auto-Shutter und manuelles Capture.';
  }
  if (step.value === 'review') {
    return 'Ecken anpassen, Filter wählen und Seite bestätigen.';
  }
  return 'Reihenfolge prüfen und als ein PDF importieren.';
});

const cameraFallbackHint = computed(() => {
  if (cameraState.value === 'denied') {
    return 'Kamera-Zugriff wurde blockiert. Erlaube Zugriff oder wähle eine Datei.';
  }
  if (cameraState.value === 'unsupported') {
    return 'Browser unterstützt keine Kamera-API für diese Seite.';
  }
  if (cameraState.value === 'loading') {
    return 'Kamera wird initialisiert…';
  }
  return 'Kamera konnte nicht gestartet werden. Du kannst stattdessen eine Datei wählen.';
});

const stateLabel = computed(() => {
  if (scanState.value === 'capturing') {
    return 'Aufnahme…';
  }
  if (scanState.value === 'locked') {
    return 'Stabil - Aufnahme gleich…';
  }
  if (scanState.value === 'tracking') {
    return 'Dokument erkannt';
  }
  return 'Suche Dokument…';
});

const showDebugOverlay = computed(() => WEBSCAN_DEBUG);

const workerHintText = computed(() => {
  if (workerState.value === 'initializing') {
    return 'Initialisiere Scanner…';
  }
  if (workerState.value === 'failed') {
    return 'Live-Erkennung nicht verfügbar (manuell aufnehmen).';
  }
  if (requestedDetectionEngine.value === 'opencv' && workerDetectionEngine.value !== 'opencv') {
    return 'OpenCV nicht geladen - Heuristik aktiv.';
  }
  return '';
});

const showCountdown = computed(
  () => scanState.value === 'locked' && autoScanEnabled.value && lockStartedAt.value > 0
);
const countdownRemainingMs = computed(() => {
  if (!showCountdown.value) {
    return LIVE_CONFIG.autoShutterDelayMs;
  }
  return clamp(
    LIVE_CONFIG.autoShutterDelayMs - (nowTs.value - lockStartedAt.value),
    0,
    LIVE_CONFIG.autoShutterDelayMs
  );
});

const countdownProgress = computed(() => {
  const elapsed = LIVE_CONFIG.autoShutterDelayMs - countdownRemainingMs.value;
  return clamp(elapsed / LIVE_CONFIG.autoShutterDelayMs, 0, 1);
});

const cropPolygon = computed(() => cropPoints.value.map((point) => `${toPercent(point.x)} ${toPercent(point.y)}`).join(', '));
const cropPolyline = computed(() => {
  const points = cropPoints.value
    .map((point) => `${toPercent(point.x)} ${toPercent(point.y)}`)
    .join(', ');
  return `${points}, ${toPercent(cropPoints.value[0]?.x || 0)} ${toPercent(cropPoints.value[0]?.y || 0)}`;
});

const editPreviewStyle = computed(() => {
  let filter = 'none';
  if (filterMode.value === 'gray') {
    filter = 'grayscale(1)';
  } else if (filterMode.value === 'document') {
    filter = 'grayscale(1) contrast(1.35) brightness(1.07)';
  }
  return { filter };
});

const rotateLabel = computed(() => rotationLabel(rotationTurns.value));

let mediaStream = null;
let analyzerWorker = null;
let analyzeCanvas = null;
let analyzeContext = null;
let frameLoopRaf = 0;
let lastCvTs = 0;
let analysisInFlight = false;
let lastRequestId = 0;
let lastAcceptedRequestId = 0;
let hasCapturedCurrentLock = false;
let lastProcessRequestId = 0;
const pendingProcessJobs = new Map();

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) {
      resetSession();
      return;
    }
    await initializeScanSession();
  }
);

watch(
  step,
  async (nextStep) => {
    if (!isOpen.value) {
      return;
    }
    if (nextStep === 'camera') {
      addVisibilityListeners();
      await startCamera();
      startFrameLoop();
      return;
    }
    stopFrameLoop();
    stopCamera();
    removeViewportListeners();
    removeVisibilityListeners();
  }
);

watch(autoScanEnabled, (enabled) => {
  if (!enabled && scanState.value === 'locked') {
    transitionToState('tracking');
  }
});

onBeforeUnmount(() => {
  detachHandleEvents();
  resetSession();
  destroyAnalyzerWorker();
});

function resolveDetectionEngineFlag() {
  const fromEnv = String(import.meta.env.VITE_WEBSCAN_DETECTION_ENGINE || '')
    .trim()
    .toLowerCase();
  if (fromEnv === 'opencv') {
    return 'opencv';
  }
  if (fromEnv === 'heuristic') {
    return 'heuristic';
  }

  if (typeof window !== 'undefined') {
    try {
      const fromStorage = String(window.localStorage?.getItem?.('pm.webscan.detectionEngine') || '')
        .trim()
        .toLowerCase();
      if (fromStorage === 'opencv') {
        return 'opencv';
      }
      if (fromStorage === 'heuristic') {
        return 'heuristic';
      }
    } catch {
      // ignore storage access failures
    }
  }

  return 'heuristic';
}

function resolveOpenCvUrlFlag() {
  return String(import.meta.env.VITE_WEBSCAN_OPENCV_URL || '').trim();
}

function makeId(prefix) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function toPercent(value) {
  return Math.round(clamp(Number(value) || 0, 0, 1) * 1000) / 10;
}

function createDefaultQuad(margin = 0.06) {
  return [
    { x: margin, y: margin },
    { x: 1 - margin, y: margin },
    { x: 1 - margin, y: 1 - margin },
    { x: margin, y: 1 - margin }
  ];
}

function cloneQuad(quad) {
  if (!Array.isArray(quad)) {
    return null;
  }
  return quad.map((point) => ({
    x: clamp(Number(point?.x) || 0, 0, 1),
    y: clamp(Number(point?.y) || 0, 0, 1)
  }));
}

function normalizeQuad(points) {
  const source = cloneQuad(points);
  if (!source || source.length !== 4) {
    return createDefaultQuad();
  }
  return source.map((point) => ({
    x: clamp(point.x, 0.01, 0.99),
    y: clamp(point.y, 0.01, 0.99)
  }));
}

function normalizeDetectionResult(payload) {
  const hasQuad = Array.isArray(payload?.quad) && payload.quad.length === 4;
  const quad = hasQuad ? normalizeQuad(payload.quad) : null;
  const confidence = hasQuad ? clamp(Number(payload?.confidence) || 0, 0, 1) : 0;

  const rawMetrics = payload?.metrics && typeof payload.metrics === 'object' ? payload.metrics : {};
  const rawBbox = rawMetrics?.bbox && typeof rawMetrics.bbox === 'object' ? rawMetrics.bbox : null;

  return {
    quad,
    confidence,
    metrics: {
      areaRatio: hasQuad ? clamp(Number(rawMetrics?.areaRatio) || 0, 0, 1) : 0,
      jitter: hasQuad ? clamp(Number(rawMetrics?.jitter) || 0, 0, 1) : 0,
      edgeStrength: hasQuad ? clamp(Number(rawMetrics?.edgeStrength) || 0, 0, 1) : 0,
      anglesScore: hasQuad ? clamp(Number(rawMetrics?.anglesScore) || 0, 0, 1) : 0,
      bbox:
        hasQuad && rawBbox
          ? {
              x: clamp(Number(rawBbox.x) || 0, 0, 1),
              y: clamp(Number(rawBbox.y) || 0, 0, 1),
              width: clamp(Number(rawBbox.width) || 0, 0, 1),
              height: clamp(Number(rawBbox.height) || 0, 0, 1)
            }
          : null
    }
  };
}

function handleStyle(point) {
  return {
    left: `${toPercent(point?.x || 0)}%`,
    top: `${toPercent(point?.y || 0)}%`
  };
}

function cleanupCapturedImage() {
  if (capturedImageUrl.value) {
    URL.revokeObjectURL(capturedImageUrl.value);
  }
  capturedImageUrl.value = '';
  capturedBlob.value = null;
  cropPoints.value = createDefaultQuad();
  filterMode.value = 'document';
  rotationTurns.value = 0;
}

function cleanupPages() {
  for (const page of pages.value) {
    if (page?.previewUrl) {
      URL.revokeObjectURL(page.previewUrl);
    }
  }
  pages.value = [];
}

function resetTrackingState() {
  scanState.value = 'searching';
  latestConfidence.value = 0;
  latestAreaRatio.value = 0;
  latestJitter.value = 0;
  latestAreaDelta.value = 0;
  latestEdgeStrength.value = 0;
  latestAnglesScore.value = 0;
  latestBbox.value = null;
  latestRawQuad.value = null;
  smoothedQuad.value = null;
  stabilitySamples.value = [];
  lockStartedAt.value = 0;
  hasCapturedCurrentLock = false;
}

function resetSession() {
  stopFrameLoop();
  stopCamera();
  removeViewportListeners();
  removeVisibilityListeners();
  clearPendingProcessJobs();
  detachHandleEvents();
  cleanupCapturedImage();
  cleanupPages();
  step.value = 'camera';
  cameraState.value = 'idle';
  resetTrackingState();
  isCapturing.value = false;
  isDetecting.value = false;
  isApplyingEdit.value = false;
  isExporting.value = false;
  draggedPageIndex.value = -1;
}

function handleDialogClose() {
  if (isBusy.value) {
    return;
  }
  isOpen.value = false;
}

async function initializeScanSession() {
  cleanupCapturedImage();
  cleanupPages();
  resetTrackingState();
  step.value = 'camera';
  await ensureAnalyzerReady();
  await nextTick();
  addVisibilityListeners();
  await startCamera();
  startFrameLoop();
}

async function ensureAnalyzerReady() {
  if (analyzerWorker) {
    workerState.value = 'ready';
    return;
  }
  if (typeof Worker === 'undefined') {
    workerState.value = 'failed';
    return;
  }

  workerState.value = 'initializing';
  try {
    analyzerWorker = new Worker(new URL('../../workers/webScanWorker.js', import.meta.url), { type: 'classic' });
    analyzerWorker.onmessage = onWorkerMessage;
    analyzerWorker.onerror = () => {
      workerState.value = 'failed';
      workerProcessingAvailable.value = false;
      analysisInFlight = false;
    };
    analyzerWorker.postMessage({
      type: 'configure',
      detectionEngine: requestedDetectionEngine.value,
      opencvUrl: OPENCV_SCRIPT_URL,
      processingEnabled: true
    });
    workerState.value = 'ready';
  } catch {
    analyzerWorker = null;
    workerState.value = 'failed';
    workerProcessingAvailable.value = false;
  }
}

function destroyAnalyzerWorker() {
  clearPendingProcessJobs();
  if (analyzerWorker) {
    analyzerWorker.terminate();
  }
  analyzerWorker = null;
  workerState.value = 'failed';
  workerProcessingAvailable.value = false;
  analysisInFlight = false;
}

async function startCamera() {
  if (!isOpen.value || step.value !== 'camera') {
    return;
  }

  if (mediaStream) {
    cameraState.value = 'ready';
    ensureOverlayCanvasSize();
    return;
  }

  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    cameraState.value = 'unsupported';
    return;
  }

  cameraState.value = 'loading';
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1920 },
        height: { ideal: 1080 }
      }
    });

    await nextTick();
    const video = videoRef.value;
    if (!(video instanceof HTMLVideoElement)) {
      throw new Error('Kamera-Vorschau konnte nicht initialisiert werden.');
    }

    video.srcObject = mediaStream;
    await video.play();
    cameraState.value = 'ready';
    ensureOverlayCanvasSize();
    addViewportListeners();
  } catch (error) {
    stopCamera();
    const name = String(error?.name || '').toLowerCase();
    if (name.includes('notallowed') || name.includes('permission')) {
      cameraState.value = 'denied';
      return;
    }
    if (name.includes('notfound') || name.includes('overconstrained')) {
      cameraState.value = 'unsupported';
      return;
    }
    cameraState.value = 'error';
  }
}

function stopCamera() {
  if (videoRef.value instanceof HTMLVideoElement) {
    videoRef.value.pause();
    videoRef.value.srcObject = null;
  }

  if (mediaStream) {
    for (const track of mediaStream.getTracks()) {
      track.stop();
    }
    mediaStream = null;
  }
}

function startFrameLoop() {
  stopFrameLoop();
  if (typeof document !== 'undefined' && document.hidden) {
    return;
  }
  nowTs.value = performance.now();

  const frame = (ts) => {
    nowTs.value = ts;
    if (!isOpen.value || step.value !== 'camera') {
      return;
    }

    ensureOverlayCanvasSize();

    if (cameraState.value === 'ready' && !(typeof document !== 'undefined' && document.hidden)) {
      maybeAnalyzeFrame(ts);
      updateScanStateMachine(ts);
      drawOverlay();
    }

    frameLoopRaf = window.requestAnimationFrame(frame);
  };

  frameLoopRaf = window.requestAnimationFrame(frame);
}

function stopFrameLoop() {
  if (frameLoopRaf) {
    window.cancelAnimationFrame(frameLoopRaf);
    frameLoopRaf = 0;
  }
  analysisInFlight = false;
  lastCvTs = 0;
}

function maybeAnalyzeFrame(ts) {
  if (typeof document !== 'undefined' && document.hidden) {
    return;
  }
  if (workerState.value !== 'ready' || !analyzerWorker) {
    return;
  }
  if (analysisInFlight || ts - lastCvTs < 1000 / LIVE_CONFIG.cvFps) {
    return;
  }

  const video = videoRef.value;
  if (!(video instanceof HTMLVideoElement)) {
    return;
  }

  const sourceWidth = Number(video.videoWidth || 0);
  const sourceHeight = Number(video.videoHeight || 0);
  if (sourceWidth <= 2 || sourceHeight <= 2) {
    return;
  }

  const size = fitSizeToLongEdge(sourceWidth, sourceHeight, LIVE_CONFIG.downscaleLongEdge);
  if (!analyzeCanvas) {
    analyzeCanvas = document.createElement('canvas');
    analyzeContext = analyzeCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  }

  if (!analyzeContext) {
    return;
  }

  analyzeCanvas.width = size.width;
  analyzeCanvas.height = size.height;
  analyzeContext.drawImage(video, 0, 0, size.width, size.height);

  try {
    const imageData = analyzeContext.getImageData(0, 0, size.width, size.height);
    analysisInFlight = true;
    lastCvTs = ts;
    lastRequestId += 1;
    analyzerWorker.postMessage(
      {
        type: 'analyze',
        requestId: lastRequestId,
        width: size.width,
        height: size.height,
        buffer: imageData.data.buffer
      },
      [imageData.data.buffer]
    );
  } catch {
    analysisInFlight = false;
  }
}

function onWorkerMessage(event) {
  const payload = event?.data || {};
  const messageType = String(payload.type || '');

  if (messageType === 'configured') {
    workerState.value = 'ready';
    workerDetectionEngine.value = String(payload.detectionEngineActive || 'heuristic');
    workerProcessingAvailable.value = Boolean(payload.processingSupported);
    return;
  }

  if (messageType === 'processResult') {
    onWorkerProcessResult(payload);
    return;
  }

  if (messageType !== 'result') {
    return;
  }

  analysisInFlight = false;
  const requestId = Number(payload.requestId || 0);
  if (requestId <= 0 || requestId < lastAcceptedRequestId) {
    return;
  }
  lastAcceptedRequestId = requestId;

  const detection = normalizeDetectionResult(payload);
  if (!detection.quad) {
    latestRawQuad.value = null;
    smoothedQuad.value = null;
    latestConfidence.value = 0;
    latestAreaRatio.value = 0;
    latestJitter.value = 0;
    latestAreaDelta.value = 0;
    latestEdgeStrength.value = 0;
    latestAnglesScore.value = 0;
    latestBbox.value = null;
    stabilitySamples.value = [];
    if (scanState.value !== 'searching' && scanState.value !== 'capturing') {
      transitionToState('searching');
    }
    return;
  }

  const quad = detection.quad;
  latestRawQuad.value = quad;
  latestConfidence.value = detection.confidence;
  latestAreaRatio.value = detection.metrics.areaRatio;
  latestEdgeStrength.value = detection.metrics.edgeStrength;
  latestAnglesScore.value = detection.metrics.anglesScore;
  latestBbox.value = detection.metrics.bbox;
  workerDetectionEngine.value = String(payload.engineUsed || workerDetectionEngine.value || 'heuristic');

  const alpha = scanState.value === 'locked' || scanState.value === 'capturing' ? 0.15 : 0.35;
  const shouldSnap = shouldSnapSmoothing(smoothedQuad.value, quad, scanState.value);
  smoothedQuad.value = smoothQuad(smoothedQuad.value, quad, alpha, shouldSnap);

  const nextSamples = stabilitySamples.value.slice();
  nextSamples.push({
    ts: nowTs.value,
    quad: cloneQuad(quad),
    areaRatio: latestAreaRatio.value,
    confidence: latestConfidence.value
  });
  if (nextSamples.length > LIVE_CONFIG.stabilitySamples) {
    nextSamples.splice(0, nextSamples.length - LIVE_CONFIG.stabilitySamples);
  }
  stabilitySamples.value = nextSamples;

  const stability = computeStability(nextSamples);
  latestJitter.value = Number.isFinite(stability.avgJitter) ? clamp(stability.avgJitter, 0, 1) : 0;
  latestAreaDelta.value = Number.isFinite(stability.avgAreaDelta) ? clamp(stability.avgAreaDelta, 0, 1) : 0;
}

function onWorkerProcessResult(payload) {
  const requestId = Number(payload?.requestId || 0);
  if (requestId <= 0) {
    return;
  }
  const pending = pendingProcessJobs.get(requestId);
  if (!pending) {
    return;
  }
  pendingProcessJobs.delete(requestId);
  if (pending.timerId) {
    window.clearTimeout(pending.timerId);
  }

  if (!payload?.supported) {
    workerProcessingAvailable.value = false;
  }

  if (payload?.ok && payload?.buffer instanceof ArrayBuffer) {
    pending.resolve({
      ok: true,
      buffer: payload.buffer,
      width: Number(payload.width) || 0,
      height: Number(payload.height) || 0
    });
    return;
  }

  pending.reject(new Error(String(payload?.error || 'Worker processing failed')));
}

function clearPendingProcessJobs() {
  for (const [, pending] of pendingProcessJobs) {
    if (pending.timerId) {
      window.clearTimeout(pending.timerId);
    }
    pending.reject(new Error('Worker process aborted'));
  }
  pendingProcessJobs.clear();
}

async function processCapturedPageWithWorker(blob, quad, selectedFilter, selectedRotation) {
  if (!(blob instanceof Blob)) {
    return null;
  }
  if (!analyzerWorker || workerState.value !== 'ready' || !workerProcessingAvailable.value) {
    return null;
  }

  const imageBuffer = await blob.arrayBuffer();
  lastProcessRequestId += 1;
  const requestId = lastProcessRequestId;

  const resultPromise = new Promise((resolve, reject) => {
    const timerId = window.setTimeout(() => {
      pendingProcessJobs.delete(requestId);
      reject(new Error('Worker processing timeout'));
    }, 10000);
    pendingProcessJobs.set(requestId, { resolve, reject, timerId });
  });

  try {
    analyzerWorker.postMessage(
      {
        type: 'processPage',
        requestId,
        imageBuffer,
        mimeType: blob.type || 'image/jpeg',
        quad,
        filterMode: selectedFilter,
        rotationTurns: selectedRotation,
        maxLongEdge: LIVE_CONFIG.maxCaptureEdge
      },
      [imageBuffer]
    );
  } catch {
    const pending = pendingProcessJobs.get(requestId);
    if (pending?.timerId) {
      window.clearTimeout(pending.timerId);
    }
    pendingProcessJobs.delete(requestId);
    return null;
  }

  try {
    const result = await resultPromise;
    if (!result?.ok || !(result.buffer instanceof ArrayBuffer)) {
      return null;
    }
    return {
      blob: new Blob([result.buffer], { type: 'image/jpeg' }),
      width: Number(result.width) || 0,
      height: Number(result.height) || 0
    };
  } catch {
    return null;
  }
}

function averageCornerMovementNormalized(previous, next) {
  if (!Array.isArray(previous) || previous.length !== 4 || !Array.isArray(next) || next.length !== 4) {
    return Number.POSITIVE_INFINITY;
  }
  let movement = 0;
  for (let i = 0; i < 4; i += 1) {
    movement += Math.hypot((next[i]?.x || 0) - (previous[i]?.x || 0), (next[i]?.y || 0) - (previous[i]?.y || 0));
  }
  return movement / 4 / Math.SQRT2;
}

function shouldSnapSmoothing(previous, next, currentState) {
  if (currentState === 'searching' || !Array.isArray(previous) || previous.length !== 4) {
    return true;
  }
  const jump = averageCornerMovementNormalized(previous, next);
  return !Number.isFinite(jump) || jump >= LIVE_CONFIG.jumpSnapThreshold;
}

function smoothQuad(previous, next, alpha, forceSnap = false) {
  const normalizedNext = normalizeQuad(next);
  if (forceSnap || !Array.isArray(previous) || previous.length !== 4) {
    return normalizedNext;
  }

  const factor = clamp(Number(alpha) || 0, 0.01, 0.95);
  return normalizedNext.map((point, index) => {
    const prior = previous[index] || point;
    return {
      x: clamp(prior.x + (point.x - prior.x) * factor, 0, 1),
      y: clamp(prior.y + (point.y - prior.y) * factor, 0, 1)
    };
  });
}

function updateScanStateMachine(ts) {
  if (scanState.value === 'capturing') {
    if (!isCapturing.value && step.value === 'camera') {
      transitionToState('tracking');
    }
    return;
  }

  const hasQuad = Array.isArray(smoothedQuad.value) && smoothedQuad.value.length === 4;
  if (!hasQuad || latestConfidence.value < LIVE_CONFIG.minConfidenceTracking) {
    if (scanState.value !== 'searching') {
      transitionToState('searching');
    }
    return;
  }

  const stability = computeStability(stabilitySamples.value);
  latestJitter.value = Number.isFinite(stability.avgJitter) ? clamp(stability.avgJitter, 0, 1) : 0;
  latestAreaDelta.value = Number.isFinite(stability.avgAreaDelta) ? clamp(stability.avgAreaDelta, 0, 1) : 0;
  const insideMargin = isQuadInsideMargin(smoothedQuad.value || latestRawQuad.value, LIVE_CONFIG.pointMargin);
  const geometryStable =
    stability.avgJitter <= LIVE_CONFIG.jitterThreshold &&
    stability.avgAreaDelta <= LIVE_CONFIG.areaChangeThreshold;
  const canEnterLocked =
    stability.windowReady &&
    stability.hasLockedConfidence &&
    geometryStable &&
    insideMargin;

  if (autoScanEnabled.value && canEnterLocked) {
    if (scanState.value !== 'locked') {
      transitionToState('locked', ts);
    }
  } else if (scanState.value !== 'tracking') {
    transitionToState('tracking');
  }

  if (scanState.value !== 'locked') {
    return;
  }

  if (
    !autoScanEnabled.value ||
    latestConfidence.value < LIVE_CONFIG.minConfidenceCountdown ||
    !geometryStable ||
    !insideMargin
  ) {
    transitionToState('tracking');
    return;
  }

  if (hasCapturedCurrentLock) {
    return;
  }

  if (ts - lockStartedAt.value >= LIVE_CONFIG.autoShutterDelayMs) {
    hasCapturedCurrentLock = true;
    transitionToState('capturing', ts);
    void captureCurrentFrame('auto');
  }
}

function computeStability(samples) {
  if (!Array.isArray(samples) || samples.length < 2) {
    return {
      windowReady: false,
      hasLockedConfidence: false,
      avgJitter: Number.POSITIVE_INFINITY,
      avgAreaDelta: Number.POSITIVE_INFINITY
    };
  }

  const window = samples.slice(-LIVE_CONFIG.stabilitySamples);
  const windowReady = window.length >= LIVE_CONFIG.stabilitySamples;
  let movementSum = 0;
  let movementCount = 0;
  let areaDeltaSum = 0;
  let areaDeltaCount = 0;

  for (let i = 1; i < window.length; i += 1) {
    const prev = window[i - 1].quad;
    const current = window[i].quad;
    if (!Array.isArray(prev) || !Array.isArray(current)) {
      continue;
    }
    for (let p = 0; p < 4; p += 1) {
      movementSum += Math.hypot(current[p].x - prev[p].x, current[p].y - prev[p].y);
      movementCount += 1;
    }
    const prevArea = clamp(Number(window[i - 1].areaRatio) || 0, 0, 1);
    const nextArea = clamp(Number(window[i].areaRatio) || 0, 0, 1);
    areaDeltaSum += Math.abs(nextArea - prevArea);
    areaDeltaCount += 1;
  }

  const avgJitter = movementCount > 0 ? movementSum / movementCount / Math.SQRT2 : Number.POSITIVE_INFINITY;
  const avgAreaDelta = areaDeltaCount > 0 ? areaDeltaSum / areaDeltaCount : Number.POSITIVE_INFINITY;
  const hasLockedConfidence = windowReady
    ? window.every((entry) => (Number(entry?.confidence) || 0) >= LIVE_CONFIG.minConfidenceLocked)
    : false;

  return { windowReady, hasLockedConfidence, avgJitter, avgAreaDelta };
}

function isQuadInsideMargin(quad, margin) {
  const normalizedMargin = clamp(Number(margin) || 0, 0, 0.2);
  if (!Array.isArray(quad) || quad.length !== 4) {
    return false;
  }
  return quad.every(
    (point) =>
      point.x >= normalizedMargin &&
      point.x <= 1 - normalizedMargin &&
      point.y >= normalizedMargin &&
      point.y <= 1 - normalizedMargin
  );
}

function transitionToState(nextState, ts = nowTs.value) {
  const normalized = String(nextState || 'searching');
  if (scanState.value === normalized) {
    return;
  }

  scanState.value = normalized;
  if (normalized === 'locked') {
    lockStartedAt.value = ts;
    hasCapturedCurrentLock = false;
    return;
  }
  if (normalized === 'capturing') {
    hasCapturedCurrentLock = true;
    return;
  }
  lockStartedAt.value = 0;
  hasCapturedCurrentLock = false;
}

function ensureOverlayCanvasSize() {
  const canvas = overlayCanvasRef.value;
  if (!(canvas instanceof HTMLCanvasElement)) {
    return;
  }
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return;
  }
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const targetWidth = Math.round(rect.width * dpr);
  const targetHeight = Math.round(rect.height * dpr);
  if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
    canvas.width = targetWidth;
    canvas.height = targetHeight;
  }
}

function drawOverlay() {
  const canvas = overlayCanvasRef.value;
  if (!(canvas instanceof HTMLCanvasElement)) {
    return;
  }
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return;
  }

  const context = canvas.getContext('2d');
  if (!context) {
    return;
  }

  const dpr = Math.max(1, window.devicePixelRatio || 1);
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);

  const onSurfaceRgb = resolveThemeRgb('--v-theme-on-surface', '15,23,42');
  const primaryRgb = resolveThemeRgb('--v-theme-primary', '59,130,246');
  drawScanHint(context, rect.width, rect.height, onSurfaceRgb);

  const video = videoRef.value;
  const layout = computeVideoLayoutForOverlay(rect.width, rect.height, video);

  const quad = smoothedQuad.value;
  if (!Array.isArray(quad) || quad.length !== 4) {
    if (showDebugOverlay.value) {
      drawDebugBbox(context, layout, onSurfaceRgb);
    }
    return;
  }

  const points = quad.map((point) => mapVideoNormPointToOverlay(point, layout));
  const isLockedVisual = scanState.value === 'locked' || scanState.value === 'capturing';
  const strokeColor = isLockedVisual
    ? `rgba(${primaryRgb}, 0.95)`
    : scanState.value === 'tracking'
    ? `rgba(${primaryRgb}, 0.58)`
    : `rgba(${onSurfaceRgb}, 0.34)`;
  const fillColor = isLockedVisual
    ? `rgba(${primaryRgb}, 0.20)`
    : scanState.value === 'tracking'
    ? `rgba(${primaryRgb}, 0.12)`
    : `rgba(${onSurfaceRgb}, 0.08)`;

  context.beginPath();
  context.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i += 1) {
    context.lineTo(points[i].x, points[i].y);
  }
  context.closePath();
  context.fillStyle = fillColor;
  context.fill();
  context.strokeStyle = strokeColor;
  context.lineWidth = isLockedVisual ? 3 : 2;
  context.stroke();

  for (const point of points) {
    context.beginPath();
    context.arc(point.x, point.y, isLockedVisual ? 4.2 : 3.6, 0, Math.PI * 2);
    context.fillStyle = strokeColor;
    context.fill();
    context.lineWidth = 1.2;
    context.strokeStyle = 'rgba(255,255,255,0.92)';
    context.stroke();
  }

  if (showCountdown.value) {
    drawQuadCountdownProgress(context, points, countdownProgress.value, primaryRgb);
  }

  if (showDebugOverlay.value) {
    drawDebugBbox(context, layout, primaryRgb);
  }
}

function drawScanHint(context, width, height, onSurfaceRgb) {
  const boxWidth = width * 0.82;
  const boxHeight = height * 0.72;
  const x = (width - boxWidth) / 2;
  const y = (height - boxHeight) / 2;

  context.save();
  context.setLineDash([8, 8]);
  context.strokeStyle = `rgba(${onSurfaceRgb}, 0.18)`;
  context.lineWidth = 1;
  context.strokeRect(x, y, boxWidth, boxHeight);
  context.restore();
}

function computeVideoLayoutForOverlay(containerWidth, containerHeight, video) {
  const videoWidth = Math.max(1, Number(video?.videoWidth) || containerWidth || 1);
  const videoHeight = Math.max(1, Number(video?.videoHeight) || containerHeight || 1);
  const scale = Math.max(containerWidth / videoWidth, containerHeight / videoHeight);
  const drawnWidth = videoWidth * scale;
  const drawnHeight = videoHeight * scale;
  return {
    videoWidth,
    videoHeight,
    scale,
    offsetX: (containerWidth - drawnWidth) * 0.5,
    offsetY: (containerHeight - drawnHeight) * 0.5
  };
}

function mapVideoNormPointToOverlay(point, layout) {
  const x = clamp(Number(point?.x) || 0, 0, 1) * layout.videoWidth;
  const y = clamp(Number(point?.y) || 0, 0, 1) * layout.videoHeight;
  return {
    x: x * layout.scale + layout.offsetX,
    y: y * layout.scale + layout.offsetY
  };
}

function drawQuadCountdownProgress(context, points, progress, primaryRgb) {
  const normalizedProgress = clamp(Number(progress) || 0, 0, 1);
  if (normalizedProgress <= 0 || !Array.isArray(points) || points.length !== 4) {
    return;
  }

  const lengths = [];
  let perimeter = 0;
  for (let i = 0; i < points.length; i += 1) {
    const start = points[i];
    const end = points[(i + 1) % points.length];
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    lengths.push(length);
    perimeter += length;
  }
  if (perimeter <= 1e-3) {
    return;
  }

  let remaining = perimeter * normalizedProgress;
  context.save();
  context.beginPath();
  context.moveTo(points[0].x, points[0].y);
  for (let i = 0; i < points.length; i += 1) {
    if (remaining <= 0) {
      break;
    }
    const start = points[i];
    const end = points[(i + 1) % points.length];
    const edgeLength = lengths[i];
    if (remaining >= edgeLength) {
      context.lineTo(end.x, end.y);
      remaining -= edgeLength;
      continue;
    }
    const t = edgeLength > 1e-6 ? remaining / edgeLength : 0;
    context.lineTo(start.x + (end.x - start.x) * t, start.y + (end.y - start.y) * t);
    remaining = 0;
  }
  context.strokeStyle = `rgba(${primaryRgb}, 0.96)`;
  context.lineWidth = 3.6;
  context.lineCap = 'round';
  context.lineJoin = 'round';
  context.stroke();
  context.restore();
}

function drawDebugBbox(context, layout, rgb) {
  const box = latestBbox.value;
  if (!showDebugOverlay.value || !box) {
    return;
  }
  const x = box.x * layout.videoWidth * layout.scale + layout.offsetX;
  const y = box.y * layout.videoHeight * layout.scale + layout.offsetY;
  const width = box.width * layout.videoWidth * layout.scale;
  const height = box.height * layout.videoHeight * layout.scale;
  if (width <= 1 || height <= 1) {
    return;
  }
  context.save();
  context.strokeStyle = `rgba(${rgb}, 0.7)`;
  context.lineWidth = 1;
  context.setLineDash([5, 3]);
  context.strokeRect(x, y, width, height);
  context.restore();
}

function resolveThemeRgb(variableName, fallback) {
  const canvas = overlayCanvasRef.value;
  const target = canvas instanceof HTMLElement ? canvas : document.documentElement;
  const computed = getComputedStyle(target).getPropertyValue(variableName).trim();
  if (/^\d+\s*,\s*\d+\s*,\s*\d+$/.test(computed)) {
    return computed;
  }
  return fallback;
}

function onViewportChanged() {
  ensureOverlayCanvasSize();
  resetTrackingState();
}

function onDocumentVisibilityChange() {
  if (!isOpen.value || step.value !== 'camera') {
    return;
  }
  if (document.hidden) {
    stopFrameLoop();
    return;
  }
  startFrameLoop();
}

function addViewportListeners() {
  window.addEventListener('resize', onViewportChanged);
  window.addEventListener('orientationchange', onViewportChanged);
}

function removeViewportListeners() {
  window.removeEventListener('resize', onViewportChanged);
  window.removeEventListener('orientationchange', onViewportChanged);
}

function addVisibilityListeners() {
  document.addEventListener('visibilitychange', onDocumentVisibilityChange);
  window.addEventListener('pagehide', onDocumentVisibilityChange);
  window.addEventListener('pageshow', onDocumentVisibilityChange);
}

function removeVisibilityListeners() {
  document.removeEventListener('visibilitychange', onDocumentVisibilityChange);
  window.removeEventListener('pagehide', onDocumentVisibilityChange);
  window.removeEventListener('pageshow', onDocumentVisibilityChange);
}

async function captureCurrentFrame(mode = 'manual') {
  if (isBusy.value || cameraState.value !== 'ready') {
    return;
  }

  const video = videoRef.value;
  if (!(video instanceof HTMLVideoElement)) {
    return;
  }

  isCapturing.value = true;
  try {
    const sourceWidth = Math.max(1, Number(video.videoWidth || 0));
    const sourceHeight = Math.max(1, Number(video.videoHeight || 0));
    if (sourceWidth <= 2 || sourceHeight <= 2) {
      throw new Error('Kein Kamerabild verfügbar.');
    }

    const size = fitSizeToLongEdge(sourceWidth, sourceHeight, LIVE_CONFIG.maxCaptureEdge);
    const canvas = document.createElement('canvas');
    canvas.width = size.width;
    canvas.height = size.height;

    const context = canvas.getContext('2d', { alpha: false });
    if (!context) {
      throw new Error('Canvas konnte nicht initialisiert werden.');
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await canvasToJpegBlob(canvas, 0.93);
    const liveQuad = cloneQuad(smoothedQuad.value || latestRawQuad.value);
    await openReviewFromCapture(blob, liveQuad, true);

    if (mode === 'auto') {
      notify({ type: 'success', message: 'Auto-Scan erfasst.' });
    }
  } catch (error) {
    if (mode === 'auto') {
      transitionToState('tracking');
    }
    notify({ type: 'error', message: mapApiError(error, 'Aufnahme fehlgeschlagen.') });
  } finally {
    isCapturing.value = false;
    if (mode === 'auto' && step.value === 'camera') {
      transitionToState('tracking');
    }
  }
}

async function openReviewFromCapture(blob, detectedQuad = null, detectIfMissing = false) {
  cleanupCapturedImage();
  capturedBlob.value = blob;
  capturedImageUrl.value = URL.createObjectURL(blob);
  filterMode.value = 'document';
  rotationTurns.value = 0;

  if (Array.isArray(detectedQuad) && detectedQuad.length === 4) {
    cropPoints.value = normalizeQuad(detectedQuad);
  } else {
    cropPoints.value = createDefaultQuad();
  }

  step.value = 'review';

  if (detectIfMissing && (!Array.isArray(detectedQuad) || detectedQuad.length !== 4)) {
    try {
      isDetecting.value = true;
      const image = await loadImageFromBlob(blob);
      await yieldToUi();
      const autoQuad = detectDocumentQuad(image, 900);
      cropPoints.value = normalizeQuad(autoQuad);
    } catch {
      cropPoints.value = createDefaultQuad();
    } finally {
      isDetecting.value = false;
    }
  }
}

function openFallbackPicker() {
  fallbackInputRef.value?.click?.();
}

async function onFallbackFileChange(event) {
  const files = Array.from(event?.target?.files || []);
  event.target.value = '';
  if (files.length <= 0) {
    return;
  }

  const file = files[0];
  const filename = String(file?.name || '').toLowerCase();
  const isPdf = String(file?.type || '').includes('pdf') || filename.endsWith('.pdf');

  if (isPdf) {
    if (emitsFiles.value) {
      emit('files-ready', {
        files: [file],
        pageCount: 0
      });
    } else {
      emit('pdf-ready', {
        file,
        pageCount: 0
      });
    }
    isOpen.value = false;
    return;
  }

  try {
    isCapturing.value = true;
    const normalizedBlob = await normalizeImageBlob(file, LIVE_CONFIG.maxCaptureEdge);
    await openReviewFromCapture(normalizedBlob, null, true);
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Bild konnte nicht geladen werden.') });
  } finally {
    isCapturing.value = false;
  }
}

function retakeCapture() {
  if (isBusy.value) {
    return;
  }
  cleanupCapturedImage();
  resetTrackingState();
  step.value = 'camera';
}

function rotateOutput() {
  rotationTurns.value = (rotationTurns.value + 1) % 4;
}

function onHandlePointerDown(event, index) {
  if (isBusy.value) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  activeHandleIndex.value = Number(index);
  activePointerId.value = Number(event.pointerId);
  attachHandleEvents();
}

function attachHandleEvents() {
  window.addEventListener('pointermove', onHandlePointerMove);
  window.addEventListener('pointerup', onHandlePointerUp);
  window.addEventListener('pointercancel', onHandlePointerUp);
}

function detachHandleEvents() {
  window.removeEventListener('pointermove', onHandlePointerMove);
  window.removeEventListener('pointerup', onHandlePointerUp);
  window.removeEventListener('pointercancel', onHandlePointerUp);
  activeHandleIndex.value = -1;
  activePointerId.value = -1;
}

function onHandlePointerMove(event) {
  if (activeHandleIndex.value < 0 || activePointerId.value !== Number(event.pointerId)) {
    return;
  }
  const image = editImageRef.value;
  if (!(image instanceof HTMLElement)) {
    return;
  }
  const rect = image.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return;
  }
  const x = clamp((event.clientX - rect.left) / rect.width, 0.01, 0.99);
  const y = clamp((event.clientY - rect.top) / rect.height, 0.01, 0.99);
  const next = cropPoints.value.slice();
  next[activeHandleIndex.value] = { x, y };
  cropPoints.value = next;
}

function onHandlePointerUp(event) {
  if (activePointerId.value !== Number(event.pointerId)) {
    return;
  }
  detachHandleEvents();
}

async function addCurrentCaptureAsPage() {
  if (!(capturedBlob.value instanceof Blob) || isBusy.value) {
    return;
  }

  isApplyingEdit.value = true;
  try {
    const processedFromWorker = await processCapturedPageWithWorker(
      capturedBlob.value,
      cropPoints.value,
      filterMode.value,
      rotationTurns.value
    );
    const processed =
      processedFromWorker ||
      (await buildProcessedPage(capturedBlob.value, cropPoints.value, filterMode.value, rotationTurns.value));
    const previewUrl = URL.createObjectURL(processed.blob);
    pages.value.push({
      id: makeId('scan-page'),
      blob: processed.blob,
      filter: filterMode.value,
      rotationTurns: rotationTurns.value,
      previewUrl
    });
    cleanupCapturedImage();
    step.value = 'pages';
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'Seite konnte nicht verarbeitet werden.') });
  } finally {
    isApplyingEdit.value = false;
  }
}

function goToCameraForNextPage() {
  if (isBusy.value) {
    return;
  }
  cleanupCapturedImage();
  resetTrackingState();
  step.value = 'camera';
}

function removePage(index) {
  const normalizedIndex = Number(index);
  if (!Number.isInteger(normalizedIndex) || normalizedIndex < 0 || normalizedIndex >= pages.value.length) {
    return;
  }
  const [removed] = pages.value.splice(normalizedIndex, 1);
  if (removed?.previewUrl) {
    URL.revokeObjectURL(removed.previewUrl);
  }
  if (pages.value.length === 0) {
    step.value = 'camera';
  }
}

function onPageDragStart(index) {
  draggedPageIndex.value = Number(index);
}

function onPageDrop(targetIndex) {
  const from = Number(draggedPageIndex.value);
  const to = Number(targetIndex);
  draggedPageIndex.value = -1;
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from === to) {
    return;
  }
  const next = pages.value.slice();
  const [moved] = next.splice(from, 1);
  if (!moved) {
    return;
  }
  next.splice(to, 0, moved);
  pages.value = next;
}

function filterLabel(mode) {
  return FILTER_OPTIONS.find((entry) => entry.value === mode)?.label || 'Original';
}

function rotationLabel(turns) {
  const normalized = ((Number(turns) || 0) % 4 + 4) % 4;
  return `${normalized * 90}°`;
}

function toTitleDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

async function exportPdfAndFinish() {
  if (pages.value.length <= 0 || isBusy.value) {
    return;
  }

  isExporting.value = true;
  try {
    if (emitsFiles.value) {
      const datePart = toTitleDate();
      const files = pages.value.map((page, index) => {
        const filename = `Scan-${datePart}-${String(index + 1).padStart(2, '0')}.jpg`;
        return new File([page.blob], filename, {
          type: page.blob?.type || 'image/jpeg',
          lastModified: Date.now()
        });
      });
      emit('files-ready', {
        files,
        pageCount: pages.value.length
      });
      isOpen.value = false;
      return;
    }

    const pdfBytes = await buildPdfFromJpegPages(pages.value.map((page) => page.blob));
    const filename = `Scan - ${toTitleDate()}.pdf`;
    const file = new File([pdfBytes], filename, {
      type: 'application/pdf',
      lastModified: Date.now()
    });

    emit('pdf-ready', {
      file,
      pageCount: pages.value.length
    });
    isOpen.value = false;
  } catch (error) {
    notify({ type: 'error', message: mapApiError(error, 'PDF konnte nicht erstellt werden.') });
  } finally {
    isExporting.value = false;
  }
}

async function buildPdfFromJpegPages(blobs) {
  const pagesForPdf = [];
  for (const blob of blobs || []) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    const size = parseJpegSize(bytes);
    pagesForPdf.push({
      width: Math.max(1, size.width),
      height: Math.max(1, size.height),
      bytes
    });
  }

  if (pagesForPdf.length <= 0) {
    throw new Error('Keine Seiten für PDF vorhanden.');
  }

  const encoder = new TextEncoder();
  const chunks = [];
  const offsets = [];
  let offset = 0;

  function pushText(text) {
    const bytes = encoder.encode(text);
    chunks.push(bytes);
    offset += bytes.length;
  }

  function pushBytes(bytes) {
    chunks.push(bytes);
    offset += bytes.length;
  }

  pushText('%PDF-1.4\n');
  pushBytes(new Uint8Array([0x25, 0xe2, 0xe3, 0xcf, 0xd3, 0x0a]));

  const pageObjectIds = [];
  const maxObjectId = 2 + pagesForPdf.length * 3;

  offsets[1] = offset;
  pushText('1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n');

  for (let index = 0; index < pagesForPdf.length; index += 1) {
    const baseId = 3 + index * 3;
    pageObjectIds.push(baseId);
  }

  offsets[2] = offset;
  pushText(`2 0 obj\n<< /Type /Pages /Count ${pagesForPdf.length} /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(' ')}] >>\nendobj\n`);

  for (let index = 0; index < pagesForPdf.length; index += 1) {
    const page = pagesForPdf[index];
    const pageObjectId = pageObjectIds[index];
    const imageObjectId = pageObjectId + 1;
    const contentObjectId = pageObjectId + 2;

    const contentStream = encoder.encode(
      `q\n${page.width} 0 0 ${page.height} 0 0 cm\n/Im0 Do\nQ\n`
    );

    offsets[pageObjectId] = offset;
    pushText(
      `${pageObjectId} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${page.width} ${page.height}] /Resources << /XObject << /Im0 ${imageObjectId} 0 R >> >> /Contents ${contentObjectId} 0 R >>\nendobj\n`
    );

    offsets[imageObjectId] = offset;
    pushText(
      `${imageObjectId} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${page.bytes.length} >>\nstream\n`
    );
    pushBytes(page.bytes);
    pushText('\nendstream\nendobj\n');

    offsets[contentObjectId] = offset;
    pushText(
      `${contentObjectId} 0 obj\n<< /Length ${contentStream.length} >>\nstream\n`
    );
    pushBytes(contentStream);
    pushText('endstream\nendobj\n');
  }

  const xrefOffset = offset;
  pushText(`xref\n0 ${maxObjectId + 1}\n`);
  pushText('0000000000 65535 f \n');
  for (let id = 1; id <= maxObjectId; id += 1) {
    const objectOffset = Number(offsets[id] || 0);
    pushText(`${String(objectOffset).padStart(10, '0')} 00000 n \n`);
  }

  pushText(`trailer\n<< /Size ${maxObjectId + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`);

  return new Blob(chunks, { type: 'application/pdf' });
}

function parseJpegSize(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 4) {
    throw new Error('Ungültige JPEG-Daten.');
  }
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) {
    throw new Error('JPEG-Header fehlt.');
  }

  let index = 2;
  while (index < bytes.length) {
    while (index < bytes.length && bytes[index] === 0xff) {
      index += 1;
    }
    if (index >= bytes.length) {
      break;
    }

    const marker = bytes[index];
    index += 1;

    if (marker === 0xd9 || marker === 0xda) {
      break;
    }

    if (index + 1 >= bytes.length) {
      break;
    }

    const segmentLength = (bytes[index] << 8) | bytes[index + 1];
    if (segmentLength < 2 || index + segmentLength > bytes.length) {
      break;
    }

    if (isSofMarker(marker) && segmentLength >= 7) {
      const height = (bytes[index + 3] << 8) | bytes[index + 4];
      const width = (bytes[index + 5] << 8) | bytes[index + 6];
      if (width > 0 && height > 0) {
        return { width, height };
      }
    }

    index += segmentLength;
  }

  throw new Error('JPEG-Größe konnte nicht gelesen werden.');
}

function isSofMarker(marker) {
  return (
    marker === 0xc0 ||
    marker === 0xc1 ||
    marker === 0xc2 ||
    marker === 0xc3 ||
    marker === 0xc5 ||
    marker === 0xc6 ||
    marker === 0xc7 ||
    marker === 0xc9 ||
    marker === 0xca ||
    marker === 0xcb ||
    marker === 0xcd ||
    marker === 0xce ||
    marker === 0xcf
  );
}

function fitSizeToLongEdge(width, height, longEdge) {
  const normalizedWidth = Math.max(1, Number(width) || 1);
  const normalizedHeight = Math.max(1, Number(height) || 1);
  const maxEdge = Math.max(normalizedWidth, normalizedHeight);
  if (maxEdge <= longEdge) {
    return { width: normalizedWidth, height: normalizedHeight };
  }
  const scale = longEdge / maxEdge;
  return {
    width: Math.max(1, Math.round(normalizedWidth * scale)),
    height: Math.max(1, Math.round(normalizedHeight * scale))
  };
}

function canvasToJpegBlob(canvas, quality = 0.92) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('Canvas export fehlgeschlagen.'));
          return;
        }
        resolve(blob);
      },
      'image/jpeg',
      quality
    );
  });
}

function loadImageFromBlob(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Bild konnte nicht dekodiert werden.'));
    };
    image.src = url;
  });
}

async function normalizeImageBlob(blob, maxEdge) {
  const image = await loadImageFromBlob(blob);
  const size = fitSizeToLongEdge(image.naturalWidth || image.width, image.naturalHeight || image.height, maxEdge);
  const canvas = document.createElement('canvas');
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext('2d', { alpha: false });
  if (!context) {
    throw new Error('Canvas konnte nicht initialisiert werden.');
  }
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvasToJpegBlob(canvas, 0.94);
}

async function buildProcessedPage(blob, quadNormalized, selectedFilter, selectedRotation) {
  const image = await loadImageFromBlob(blob);
  const sourceCanvas = document.createElement('canvas');
  sourceCanvas.width = image.naturalWidth || image.width;
  sourceCanvas.height = image.naturalHeight || image.height;
  const sourceContext = sourceCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!sourceContext) {
    throw new Error('Bildverarbeitung nicht verfügbar.');
  }
  sourceContext.drawImage(image, 0, 0, sourceCanvas.width, sourceCanvas.height);

  const quad = mapQuadToVideoPixels(quadNormalized, sourceCanvas.width, sourceCanvas.height);

  await yieldToUi();
  const warpedCanvas = warpPerspective(sourceCanvas, quad);
  applyFilterToCanvas(warpedCanvas, selectedFilter);
  const rotatedCanvas = rotateCanvasByTurns(warpedCanvas, selectedRotation);

  const outputBlob = await canvasToJpegBlob(rotatedCanvas, 0.9);
  return {
    blob: outputBlob,
    width: rotatedCanvas.width,
    height: rotatedCanvas.height
  };
}

function detectDocumentQuad(image, targetLongEdge = 900) {
  const sourceWidth = image.naturalWidth || image.width;
  const sourceHeight = image.naturalHeight || image.height;
  const size = fitSizeToLongEdge(sourceWidth, sourceHeight, targetLongEdge);

  const canvas = document.createElement('canvas');
  canvas.width = size.width;
  canvas.height = size.height;
  const context = canvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!context) {
    return createDefaultQuad();
  }

  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  const frame = context.getImageData(0, 0, canvas.width, canvas.height);
  const width = frame.width;
  const height = frame.height;
  const pixels = frame.data;
  const gray = new Float32Array(width * height);

  for (let i = 0, p = 0; i < gray.length; i += 1, p += 4) {
    gray[i] = pixels[p] * 0.299 + pixels[p + 1] * 0.587 + pixels[p + 2] * 0.114;
  }

  const gradient = new Float32Array(width * height);
  let sum = 0;
  let sumSquares = 0;
  let count = 0;

  for (let y = 1; y < height - 1; y += 1) {
    const rowOffset = y * width;
    for (let x = 1; x < width - 1; x += 1) {
      const index = rowOffset + x;
      const gx = gray[index + 1] - gray[index - 1];
      const gy = gray[index + width] - gray[index - width];
      const magnitude = Math.abs(gx) + Math.abs(gy);
      gradient[index] = magnitude;
      sum += magnitude;
      sumSquares += magnitude * magnitude;
      count += 1;
    }
  }

  if (count <= 0) {
    return createDefaultQuad();
  }

  const mean = sum / count;
  const variance = Math.max(0, sumSquares / count - mean * mean);
  const threshold = mean + Math.sqrt(variance) * 1.15;

  const leftSamples = [];
  const rightSamples = [];
  const rowStart = Math.floor(height * 0.06);
  const rowEnd = Math.ceil(height * 0.94);
  for (let y = rowStart; y < rowEnd; y += 1) {
    let left = -1;
    let right = -1;
    const offset = y * width;

    for (let x = 1; x < width - 1; x += 1) {
      if (gradient[offset + x] > threshold) {
        left = x;
        break;
      }
    }

    for (let x = width - 2; x >= 1; x -= 1) {
      if (gradient[offset + x] > threshold) {
        right = x;
        break;
      }
    }

    if (left >= 0 && right >= 0 && right - left > width * 0.24) {
      leftSamples.push({ x: left, y });
      rightSamples.push({ x: right, y });
    }
  }

  const topSamples = [];
  const bottomSamples = [];
  const colStart = Math.floor(width * 0.06);
  const colEnd = Math.ceil(width * 0.94);
  for (let x = colStart; x < colEnd; x += 1) {
    let top = -1;
    let bottom = -1;

    for (let y = 1; y < height - 1; y += 1) {
      if (gradient[y * width + x] > threshold) {
        top = y;
        break;
      }
    }

    for (let y = height - 2; y >= 1; y -= 1) {
      if (gradient[y * width + x] > threshold) {
        bottom = y;
        break;
      }
    }

    if (top >= 0 && bottom >= 0 && bottom - top > height * 0.24) {
      topSamples.push({ x, y: top });
      bottomSamples.push({ x, y: bottom });
    }
  }

  if (leftSamples.length < 20 || rightSamples.length < 20 || topSamples.length < 20 || bottomSamples.length < 20) {
    return createDefaultQuad();
  }

  const topLine = fitLineYFromX(topSamples);
  const bottomLine = fitLineYFromX(bottomSamples);
  const leftLine = fitLineXFromY(leftSamples);
  const rightLine = fitLineXFromY(rightSamples);
  if (!topLine || !bottomLine || !leftLine || !rightLine) {
    return createDefaultQuad();
  }

  const topLeft = intersectLines(topLine, leftLine);
  const topRight = intersectLines(topLine, rightLine);
  const bottomRight = intersectLines(bottomLine, rightLine);
  const bottomLeft = intersectLines(bottomLine, leftLine);

  const corners = [topLeft, topRight, bottomRight, bottomLeft].map((point) => ({
    x: clamp(point?.x || 0, 0, width - 1),
    y: clamp(point?.y || 0, 0, height - 1)
  }));

  const area = polygonArea(corners);
  const ratio = area / Math.max(1, width * height);
  if (!Number.isFinite(ratio) || ratio < 0.12) {
    return createDefaultQuad();
  }

  return corners.map((point) => ({
    x: clamp(point.x / width, 0.01, 0.99),
    y: clamp(point.y / height, 0.01, 0.99)
  }));
}

function fitLineYFromX(samples) {
  let sx = 0;
  let sy = 0;
  let sxy = 0;
  let sxx = 0;
  for (const point of samples) {
    sx += point.x;
    sy += point.y;
    sxy += point.x * point.y;
    sxx += point.x * point.x;
  }
  const n = samples.length;
  const denominator = n * sxx - sx * sx;
  if (Math.abs(denominator) < 1e-6) {
    return null;
  }
  const a = (n * sxy - sx * sy) / denominator;
  const b = (sy - a * sx) / n;
  return { a, b };
}

function fitLineXFromY(samples) {
  let sx = 0;
  let sy = 0;
  let sxy = 0;
  let syy = 0;
  for (const point of samples) {
    sx += point.x;
    sy += point.y;
    sxy += point.x * point.y;
    syy += point.y * point.y;
  }
  const n = samples.length;
  const denominator = n * syy - sy * sy;
  if (Math.abs(denominator) < 1e-6) {
    return null;
  }
  const a = (n * sxy - sx * sy) / denominator;
  const b = (sx - a * sy) / n;
  return { a, b };
}

function intersectLines(lineY, lineX) {
  const denominator = 1 - lineY.a * lineX.a;
  if (Math.abs(denominator) < 1e-6) {
    return { x: 0, y: 0 };
  }
  const y = (lineY.a * lineX.b + lineY.b) / denominator;
  const x = lineX.a * y + lineX.b;
  return { x, y };
}

function polygonArea(points) {
  let area = 0;
  for (let i = 0; i < points.length; i += 1) {
    const current = points[i];
    const next = points[(i + 1) % points.length];
    area += current.x * next.y - next.x * current.y;
  }
  return Math.abs(area) * 0.5;
}

function distance(pointA, pointB) {
  return Math.hypot((pointA?.x || 0) - (pointB?.x || 0), (pointA?.y || 0) - (pointB?.y || 0));
}

function mapQuadToVideoPixels(quadNorm, videoWidth, videoHeight) {
  const width = Math.max(1, Number(videoWidth) || 1);
  const height = Math.max(1, Number(videoHeight) || 1);
  return normalizeQuad(quadNorm).map((point) => ({
    x: point.x * width,
    y: point.y * height
  }));
}

function warpPerspective(sourceCanvas, quad) {
  const widthEstimate = Math.max(distance(quad[0], quad[1]), distance(quad[3], quad[2]));
  const heightEstimate = Math.max(distance(quad[0], quad[3]), distance(quad[1], quad[2]));
  const outputSize = fitSizeToLongEdge(Math.max(1, Math.round(widthEstimate)), Math.max(1, Math.round(heightEstimate)), LIVE_CONFIG.maxCaptureEdge);

  const destinationCanvas = document.createElement('canvas');
  destinationCanvas.width = Math.max(1, outputSize.width);
  destinationCanvas.height = Math.max(1, outputSize.height);

  const srcContext = sourceCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  const dstContext = destinationCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!srcContext || !dstContext) {
    return sourceCanvas;
  }

  const srcFrame = srcContext.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
  const dstFrame = dstContext.createImageData(destinationCanvas.width, destinationCanvas.height);

  const homography = solveRectToQuadHomography(quad, destinationCanvas.width, destinationCanvas.height);
  if (!homography) {
    return sourceCanvas;
  }

  const srcPixels = srcFrame.data;
  const dstPixels = dstFrame.data;
  const srcWidth = sourceCanvas.width;
  const srcHeight = sourceCanvas.height;

  for (let y = 0; y < destinationCanvas.height; y += 1) {
    for (let x = 0; x < destinationCanvas.width; x += 1) {
      const mapped = applyHomography(homography, x, y);
      const dstOffset = (y * destinationCanvas.width + x) * 4;
      sampleBilinear(srcPixels, srcWidth, srcHeight, mapped.x, mapped.y, dstPixels, dstOffset);
    }
  }

  dstContext.putImageData(dstFrame, 0, 0);
  return destinationCanvas;
}

function solveRectToQuadHomography(quad, width, height) {
  const destination = [
    { x: 0, y: 0 },
    { x: width - 1, y: 0 },
    { x: width - 1, y: height - 1 },
    { x: 0, y: height - 1 }
  ];

  const matrix = [];
  const vector = [];

  for (let i = 0; i < 4; i += 1) {
    const dx = destination[i].x;
    const dy = destination[i].y;
    const sx = quad[i].x;
    const sy = quad[i].y;

    matrix.push([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy]);
    vector.push(sx);
    matrix.push([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy]);
    vector.push(sy);
  }

  const solution = solveLinearSystem(matrix, vector);
  if (!solution) {
    return null;
  }

  return {
    a: solution[0],
    b: solution[1],
    c: solution[2],
    d: solution[3],
    e: solution[4],
    f: solution[5],
    g: solution[6],
    h: solution[7]
  };
}

function solveLinearSystem(matrixInput, vectorInput) {
  const n = vectorInput.length;
  const matrix = matrixInput.map((row) => row.slice());
  const vector = vectorInput.slice();

  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < n; row += 1) {
      if (Math.abs(matrix[row][col]) > Math.abs(matrix[pivot][col])) {
        pivot = row;
      }
    }

    if (Math.abs(matrix[pivot][col]) < 1e-10) {
      return null;
    }

    if (pivot !== col) {
      [matrix[col], matrix[pivot]] = [matrix[pivot], matrix[col]];
      [vector[col], vector[pivot]] = [vector[pivot], vector[col]];
    }

    const pivotValue = matrix[col][col];
    for (let j = col; j < n; j += 1) {
      matrix[col][j] /= pivotValue;
    }
    vector[col] /= pivotValue;

    for (let row = 0; row < n; row += 1) {
      if (row === col) {
        continue;
      }
      const factor = matrix[row][col];
      if (Math.abs(factor) < 1e-12) {
        continue;
      }
      for (let j = col; j < n; j += 1) {
        matrix[row][j] -= factor * matrix[col][j];
      }
      vector[row] -= factor * vector[col];
    }
  }

  return vector;
}

function applyHomography(h, x, y) {
  const denominator = h.g * x + h.h * y + 1;
  if (Math.abs(denominator) < 1e-8) {
    return { x: -1, y: -1 };
  }
  return {
    x: (h.a * x + h.b * y + h.c) / denominator,
    y: (h.d * x + h.e * y + h.f) / denominator
  };
}

function sampleBilinear(srcPixels, srcWidth, srcHeight, x, y, dstPixels, dstOffset) {
  if (x < 0 || y < 0 || x > srcWidth - 1 || y > srcHeight - 1) {
    dstPixels[dstOffset] = 255;
    dstPixels[dstOffset + 1] = 255;
    dstPixels[dstOffset + 2] = 255;
    dstPixels[dstOffset + 3] = 255;
    return;
  }

  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(srcWidth - 1, x0 + 1);
  const y1 = Math.min(srcHeight - 1, y0 + 1);
  const dx = x - x0;
  const dy = y - y0;

  const i00 = (y0 * srcWidth + x0) * 4;
  const i10 = (y0 * srcWidth + x1) * 4;
  const i01 = (y1 * srcWidth + x0) * 4;
  const i11 = (y1 * srcWidth + x1) * 4;

  for (let c = 0; c < 3; c += 1) {
    const v00 = srcPixels[i00 + c];
    const v10 = srcPixels[i10 + c];
    const v01 = srcPixels[i01 + c];
    const v11 = srcPixels[i11 + c];

    const top = v00 + (v10 - v00) * dx;
    const bottom = v01 + (v11 - v01) * dx;
    dstPixels[dstOffset + c] = Math.round(top + (bottom - top) * dy);
  }
  dstPixels[dstOffset + 3] = 255;
}

function applyFilterToCanvas(canvas, selectedFilter) {
  if (selectedFilter === 'original') {
    return;
  }

  const context = canvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!context) {
    return;
  }

  const frame = context.getImageData(0, 0, canvas.width, canvas.height);
  const data = frame.data;

  if (selectedFilter === 'gray') {
    for (let i = 0; i < data.length; i += 4) {
      const gray = Math.round(data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114);
      data[i] = gray;
      data[i + 1] = gray;
      data[i + 2] = gray;
    }
    context.putImageData(frame, 0, 0);
    return;
  }

  const gray = new Uint8ClampedArray(data.length / 4);
  for (let i = 0, p = 0; i < gray.length; i += 1, p += 4) {
    gray[i] = Math.round(data[p] * 0.299 + data[p + 1] * 0.587 + data[p + 2] * 0.114);
  }

  const width = canvas.width;
  const height = canvas.height;
  const sharpened = new Uint8ClampedArray(gray.length);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (x === 0 || y === 0 || x === width - 1 || y === height - 1) {
        sharpened[index] = gray[index];
        continue;
      }
      const center = gray[index] * 1.6;
      const around = (gray[index - 1] + gray[index + 1] + gray[index - width] + gray[index + width]) * 0.15;
      sharpened[index] = clamp(Math.round(center - around), 0, 255);
    }
  }

  for (let i = 0, p = 0; i < sharpened.length; i += 1, p += 4) {
    const contrasted = clamp(Math.round((sharpened[i] - 128) * 1.55 + 132), 0, 255);
    const leveled = contrasted > 242 ? 255 : contrasted;
    data[p] = leveled;
    data[p + 1] = leveled;
    data[p + 2] = leveled;
  }

  context.putImageData(frame, 0, 0);
}

function rotateCanvasByTurns(canvas, turns) {
  const normalizedTurns = ((Number(turns) || 0) % 4 + 4) % 4;
  if (normalizedTurns === 0) {
    return canvas;
  }

  const rotated = document.createElement('canvas');
  if (normalizedTurns % 2 === 0) {
    rotated.width = canvas.width;
    rotated.height = canvas.height;
  } else {
    rotated.width = canvas.height;
    rotated.height = canvas.width;
  }

  const context = rotated.getContext('2d', { alpha: false });
  if (!context) {
    return canvas;
  }

  if (normalizedTurns === 1) {
    context.translate(rotated.width, 0);
    context.rotate(Math.PI / 2);
  } else if (normalizedTurns === 2) {
    context.translate(rotated.width, rotated.height);
    context.rotate(Math.PI);
  } else {
    context.translate(0, rotated.height);
    context.rotate(-Math.PI / 2);
  }

  context.drawImage(canvas, 0, 0);
  return rotated;
}

function yieldToUi() {
  return new Promise((resolve) => {
    window.setTimeout(resolve, 0);
  });
}
</script>

<style scoped>
.web-scan {
  min-height: 640px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.web-scan__camera,
.web-scan__review,
.web-scan__pages {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.web-scan__camera-shell {
  position: relative;
  flex: 1 1 auto;
  min-height: 420px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 20px;
  background: rgba(10, 14, 24, 0.96);
  overflow: hidden;
}

.web-scan__video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: #0f172a;
}

.web-scan__video.is-hidden {
  opacity: 0;
}

.web-scan__overlay-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.web-scan__camera-fallback {
  position: absolute;
  inset: 0;
  padding: 24px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 8px;
  text-align: center;
  color: rgba(255, 255, 255, 0.86);
  background: rgba(10, 14, 24, 0.7);
}

.web-scan__camera-fallback-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.web-scan__camera-fallback-text {
  margin: 0;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.7);
  max-width: 560px;
}

.web-scan__hud {
  position: absolute;
  top: 12px;
  display: inline-flex;
  gap: 8px;
  align-items: center;
  z-index: 3;
}

.web-scan__hud--left {
  left: 12px;
}

.web-scan__state-chip,
.web-scan__metric-chip {
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.77rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.web-scan__state-chip {
  color: rgba(255, 255, 255, 0.95);
  background: rgba(15, 23, 42, 0.6);
}

.web-scan__state-chip.is-searching {
  background: rgba(15, 23, 42, 0.64);
}

.web-scan__state-chip.is-tracking {
  background: rgba(var(--v-theme-primary), 0.36);
}

.web-scan__state-chip.is-locked {
  background: rgba(var(--v-theme-primary), 0.6);
}

.web-scan__state-chip.is-capturing {
  background: rgba(var(--v-theme-primary), 0.74);
}

.web-scan__metric-chip {
  color: rgba(255, 255, 255, 0.86);
  background: rgba(15, 23, 42, 0.54);
}

.web-scan__init-hint {
  position: absolute;
  left: 50%;
  bottom: 14px;
  transform: translateX(-50%);
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.84);
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.14);
}

.web-scan__debug-panel {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 3;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(7, 12, 20, 0.64);
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.72rem;
  line-height: 1.35;
}

.web-scan__camera-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.web-scan__auto-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.86rem;
  color: rgba(var(--v-theme-on-surface), 0.76);
}

.web-scan__auto-toggle input {
  margin: 0;
}

.web-scan__edit-stage {
  flex: 1 1 auto;
  min-height: 0;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 18px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  display: grid;
  place-items: center;
  padding: 12px;
  overflow: auto;
}

.web-scan__image-wrap {
  position: relative;
  width: min(100%, 820px);
}

.web-scan__edit-image {
  display: block;
  width: 100%;
  max-height: min(62vh, 640px);
  object-fit: contain;
  border-radius: 10px;
  background: #0f172a;
  user-select: none;
}

.web-scan__overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.web-scan__overlay-fill {
  fill: rgba(var(--v-theme-primary), 0.13);
}

.web-scan__overlay-line {
  fill: none;
  stroke: rgba(var(--v-theme-primary), 0.92);
  stroke-width: 0.9;
}

.web-scan__handle {
  position: absolute;
  width: 20px;
  height: 20px;
  margin-left: -10px;
  margin-top: -10px;
  border-radius: 999px;
  border: 2px solid #ffffff;
  background: rgb(var(--v-theme-primary));
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.28);
  touch-action: none;
}

.web-scan__filters {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
}

.web-scan__filter-btn {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.16);
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.03);
  min-height: 34px;
  padding: 0 14px;
  font-size: 0.84rem;
  cursor: pointer;
}

.web-scan__filter-btn.is-active {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: rgba(var(--v-theme-primary), 0.12);
  color: rgb(var(--v-theme-primary));
}

.web-scan__edit-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.web-scan__edit-actions {
  display: inline-flex;
  gap: 8px;
  flex-wrap: wrap;
}

.web-scan__subtle {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.web-scan__pages-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.web-scan__pages-header h3 {
  margin: 0;
  font-size: 1rem;
}

.web-scan__pages-header p {
  margin: 2px 0 0;
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.64);
}

.web-scan__page-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 8px;
  align-content: start;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 16px;
  padding: 8px;
}

.web-scan__page-row {
  display: grid;
  grid-template-columns: 34px 66px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.web-scan__page-index {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.78rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.72);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.web-scan__page-thumb {
  width: 66px;
  height: 84px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: #ffffff;
}

.web-scan__page-meta {
  min-width: 0;
}

.web-scan__page-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.88);
}

.web-scan__page-subline {
  margin-top: 2px;
  font-size: 0.78rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.web-scan__pages-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 760px) {
  .web-scan {
    min-height: 600px;
  }

  .web-scan__camera-shell {
    min-height: 340px;
  }

  .web-scan__page-row {
    grid-template-columns: 30px 54px minmax(0, 1fr) auto;
    gap: 8px;
  }

  .web-scan__page-thumb {
    width: 54px;
    height: 72px;
  }
}
</style>

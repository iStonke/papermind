<template>
  <div class="ave">
    <!-- Fehlerzustand -->
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      density="comfortable"
      class="ave__alert"
    >
      {{ error }}
    </v-alert>

    <!-- Zuschnitt-Editor (Bild geladen) -->
    <div v-if="imgLoaded" class="ave__editor">
      <div
        class="ave__stage"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointerleave="onPointerUp"
      >
        <canvas ref="canvasRef" class="ave__canvas" />
        <div class="ave__grid" aria-hidden="true" />
      </div>

      <div class="ave__controls">
        <h3 class="ave__title">Zuschnitt anpassen</h3>
        <p class="ave__desc">
          Ziehe das Bild und zoome für einen quadratischen Ausschnitt. Live-Vorschau links.
        </p>
        <div class="ave__zoom">
          <v-icon size="18">mdi-magnify-minus-outline</v-icon>
          <v-slider
            v-model="zoom"
            :min="1"
            :max="3"
            :step="0.01"
            hide-details
            density="compact"
            color="primary"
          />
          <v-icon size="18">mdi-magnify-plus-outline</v-icon>
        </div>
        <div class="ave__fileinfo">{{ fileInfo }}</div>
      </div>
    </div>

    <!-- Drop-Zone (kein Bild / Fehler → neue Datei wählen) -->
    <div
      v-else
      class="ave__dropzone"
      :class="{ 'ave__dropzone--error': !!error, 'ave__dropzone--over': dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <div class="ave__dropcircle">
        <v-icon size="40">{{ error ? 'mdi-close' : 'mdi-tray-arrow-up' }}</v-icon>
      </div>
      <div class="ave__droptext">
        <h3 class="ave__title">{{ error ? 'Andere Datei wählen' : 'Bild hierher ziehen' }}</h3>
        <p class="ave__desc">
          Ziehe ein Bild hierher oder wähle eine Datei. Quadratisch wird empfohlen.
        </p>
        <p class="ave__formats">PNG · JPEG · WEBP · MAX. {{ MAX_MB }} MB</p>
        <v-btn variant="flat" color="primary" size="small" @click="pickFile">Datei auswählen</v-btn>
      </div>
    </div>

    <!-- Aktuelles Bild entfernen -->
    <div v-if="hasCurrentAvatar" class="ave__remove">
      <span class="ave__remove-hint">
        Aktuelles Bild kann jederzeit entfernt werden → zurück zum Initialen-Kreis.
      </span>
      <v-btn
        variant="outlined"
        color="error"
        size="small"
        :loading="removing"
        @click="remove"
      >
        Entfernen
      </v-btn>
    </div>

    <input
      ref="fileInput"
      type="file"
      accept="image/png,image/jpeg,image/webp"
      class="d-none"
      @change="onFileSelected"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, ref, shallowRef, watch } from 'vue';

import { deleteAvatar, uploadAvatar } from '../../api/auth.js';
import { useAuthStore } from '../../stores/auth.js';
import { notifyError, useNotifications } from '../../stores/notifications';

const MAX_MB = 5;
const MAX_BYTES = MAX_MB * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MIN_DIM = 128;
const VIEW = 240; // Anzeige-/Bezugsgröße des Zuschnitts
const EXPORT = 512; // Export-Kantenlänge

const emit = defineEmits(['done']);

const auth = useAuthStore();
const { notify } = useNotifications();

const fileInput = ref(null);
const canvasRef = ref(null);
const img = shallowRef(null);
const imgLoaded = ref(false);
const error = ref('');
const dragOver = ref(false);
const applying = ref(false);
const removing = ref(false);

const zoom = ref(1);
const offset = { x: 0, y: 0 };
let dragging = false;
let lastPointer = { x: 0, y: 0 };

const fileMeta = ref({ name: '', size: 0, w: 0, h: 0 });

const hasCurrentAvatar = computed(() => !!auth.user?.has_avatar);
const fileInfo = computed(() => {
  const m = fileMeta.value;
  if (!m.name) return '';
  const mb = (m.size / (1024 * 1024)).toFixed(1).replace('.', ',');
  return `${m.name} · ${mb} MB · ${m.w} × ${m.h}`;
});

watch(zoom, () => {
  clampOffset();
  draw();
});

function pickFile() {
  fileInput.value?.click();
}

function onFileSelected(event) {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (file) handleFile(file);
}

function onDrop(event) {
  dragOver.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) handleFile(file);
}

function handleFile(file) {
  error.value = '';
  if (!ALLOWED_TYPES.includes(file.type)) {
    fail(`Falsches Format. „${file.name}" wird nicht unterstützt — erlaubt sind PNG, JPEG, WEBP.`);
    return;
  }
  if (file.size > MAX_BYTES) {
    const mb = (file.size / (1024 * 1024)).toFixed(1).replace('.', ',');
    fail(`Datei zu groß. „${file.name}" ist ${mb} MB — erlaubt sind max. ${MAX_MB} MB.`);
    return;
  }

  const url = URL.createObjectURL(file);
  const image = new Image();
  image.onload = async () => {
    if (image.naturalWidth < MIN_DIM || image.naturalHeight < MIN_DIM) {
      URL.revokeObjectURL(url);
      fail(`Auflösung zu klein (min. ${MIN_DIM} px).`);
      return;
    }
    img.value = image;
    fileMeta.value = {
      name: file.name,
      size: file.size,
      w: image.naturalWidth,
      h: image.naturalHeight,
    };
    zoom.value = 1;
    offset.x = 0;
    offset.y = 0;
    error.value = '';
    imgLoaded.value = true;
    await nextTick();
    draw();
  };
  image.onerror = () => {
    URL.revokeObjectURL(url);
    fail('Die Datei konnte nicht als Bild gelesen werden (evtl. beschädigt).');
  };
  image.src = url;
}

function fail(message) {
  error.value = message;
  img.value = null;
  imgLoaded.value = false;
}

function coverScale() {
  const iw = img.value.naturalWidth;
  const ih = img.value.naturalHeight;
  return Math.max(VIEW / iw, VIEW / ih);
}

function drawDims() {
  const scale = coverScale() * zoom.value;
  return { dw: img.value.naturalWidth * scale, dh: img.value.naturalHeight * scale };
}

function clampOffset() {
  if (!img.value) return;
  const { dw, dh } = drawDims();
  const maxX = Math.max(0, (dw - VIEW) / 2);
  const maxY = Math.max(0, (dh - VIEW) / 2);
  offset.x = Math.min(maxX, Math.max(-maxX, offset.x));
  offset.y = Math.min(maxY, Math.max(-maxY, offset.y));
}

function draw() {
  const canvas = canvasRef.value;
  if (!canvas || !img.value) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = VIEW * dpr;
  canvas.height = VIEW * dpr;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, VIEW, VIEW);
  const { dw, dh } = drawDims();
  const x = (VIEW - dw) / 2 + offset.x;
  const y = (VIEW - dh) / 2 + offset.y;
  ctx.drawImage(img.value, x, y, dw, dh);
}

function onPointerDown(event) {
  if (!imgLoaded.value) return;
  dragging = true;
  lastPointer = { x: event.clientX, y: event.clientY };
  event.target.setPointerCapture?.(event.pointerId);
}
function onPointerMove(event) {
  if (!dragging) return;
  offset.x += event.clientX - lastPointer.x;
  offset.y += event.clientY - lastPointer.y;
  lastPointer = { x: event.clientX, y: event.clientY };
  clampOffset();
  draw();
}
function onPointerUp() {
  dragging = false;
}

function exportBlob() {
  return new Promise((resolve) => {
    const out = document.createElement('canvas');
    out.width = EXPORT;
    out.height = EXPORT;
    const ctx = out.getContext('2d');
    const factor = EXPORT / VIEW;
    ctx.setTransform(factor, 0, 0, factor, 0, 0);
    const { dw, dh } = drawDims();
    const x = (VIEW - dw) / 2 + offset.x;
    const y = (VIEW - dh) / 2 + offset.y;
    ctx.drawImage(img.value, x, y, dw, dh);
    out.toBlob((blob) => resolve(blob), 'image/webp', 0.9);
  });
}

const canApply = computed(() => imgLoaded.value && !error.value);

async function apply() {
  if (!canApply.value) return;
  applying.value = true;
  try {
    const blob = await exportBlob();
    const file = new File([blob], 'avatar.webp', { type: 'image/webp' });
    const updated = await uploadAvatar(file);
    auth.setUser(updated);
    notify({ type: 'success', message: 'Profilbild aktualisiert.' });
    emit('done');
  } catch (err) {
    notifyError(err, 'Profilbild konnte nicht hochgeladen werden.');
  } finally {
    applying.value = false;
  }
}

async function remove() {
  removing.value = true;
  try {
    const updated = await deleteAvatar();
    auth.setUser(updated);
    notify({ type: 'success', message: 'Profilbild entfernt.' });
    emit('done');
  } catch (err) {
    notifyError(err, 'Profilbild konnte nicht entfernt werden.');
  } finally {
    removing.value = false;
  }
}

defineExpose({ canApply, applying, hasImage: imgLoaded, pickFile, apply });
</script>

<style scoped>
.ave {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 560px;
  margin-inline: auto;
}
.ave__alert {
  margin: 0;
}

/* Editor */
.ave__editor {
  display: flex;
  gap: 28px;
  align-items: center;
  flex-wrap: wrap;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.22);
  border-radius: 18px;
  padding: 22px;
}
.ave__stage {
  position: relative;
  width: 240px;
  height: 240px;
  flex: 0 0 auto;
  border-radius: 50%;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
  border: 2px solid rgba(var(--v-theme-primary), 0.7);
  background: rgba(var(--v-theme-on-surface), 0.05);
}
.ave__stage:active {
  cursor: grabbing;
}
.ave__canvas {
  width: 240px;
  height: 240px;
  display: block;
}
.ave__grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.5) 1px, transparent 1px);
  background-size: 80px 80px;
  background-position: center;
  opacity: 0.5;
}
.ave__controls {
  flex: 1 1 240px;
  min-width: 220px;
}
.ave__zoom {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
}
.ave__fileinfo {
  margin-top: 12px;
  font-size: 0.78rem;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.55);
  text-transform: uppercase;
}

/* Drop-Zone */
.ave__dropzone {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 14px;
  border: 2px dashed rgba(var(--v-theme-on-surface), 0.22);
  border-radius: 18px;
  padding: 36px 28px;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.ave__dropzone--over {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.05);
}
.ave__dropzone--error {
  border-color: rgba(var(--v-theme-error), 0.5);
  background: rgba(var(--v-theme-error), 0.04);
}
.ave__dropcircle {
  flex: 0 0 auto;
  width: 84px;
  height: 84px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
}
.ave__dropzone--error .ave__dropcircle {
  background: rgba(var(--v-theme-error), 0.12);
  color: rgb(var(--v-theme-error));
}
.ave__droptext {
  max-width: 380px;
}
.ave__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}
.ave__desc {
  font-size: 0.86rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
  margin: 6px 0 0;
  line-height: 1.4;
}
.ave__formats {
  font-size: 0.76rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.5);
  margin: 10px 0 12px;
}

/* Entfernen-Zeile */
.ave__remove {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 4px;
}
.ave__remove-hint {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>

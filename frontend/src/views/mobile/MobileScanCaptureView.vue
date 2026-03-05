<template>
  <main class="mobile-scan-capture" @pointerdown="onFirstInteraction">
    <section class="mobile-scan-capture__card">
      <header class="mobile-scan-capture__header">
        <p class="mobile-scan-capture__eyebrow">PaperMind</p>
        <h1>Dokument fotografieren</h1>
        <p>Halte das Dokument vollständig ins Bild.</p>
      </header>

      <input
        ref="fileInputRef"
        class="mobile-scan-capture__input"
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        @change="onFileInputChange"
      />

      <button
        type="button"
        class="mobile-scan-capture__action"
        :disabled="isActionDisabled"
        @click.stop.prevent="openPickerFromButton"
      >
        {{ actionLabel }}
      </button>

      <p class="mobile-scan-capture__hint">{{ hintText }}</p>

      <div class="mobile-scan-capture__meta">
        <p v-if="expiresLabel" class="mobile-scan-capture__expires">{{ expiresLabel }}</p>
      </div>

      <p class="mobile-scan-capture__status" :class="`is-${statusTone}`">{{ statusMessage }}</p>
      <p v-if="uploadedTotal > 0" class="mobile-scan-capture__uploaded">
        Bereits verarbeitet: {{ uploadedTotal }} PDF-Upload{{ uploadedTotal === 1 ? '' : 's' }}.
      </p>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import { getPhoneScanStatus, uploadPhoneScanFiles } from '../../api/phoneScan';

const props = defineProps({
  initialToken: { type: String, default: '' },
  apiBaseUrl: { type: String, default: '' }
});

const fileInputRef = ref(null);
const token = ref('');
const isUploading = ref(false);
const uploadedTotal = ref(0);
const sessionState = ref('waiting');
const statusMessage = ref('Bereit zum Fotografieren.');
const statusTone = ref('neutral');
const expiresAt = ref('');
const expiresLabel = ref('');
const hasInteracted = ref(false);
const autoOpenAttempted = ref(false);

let pollTimer = null;
let countdownTimer = null;

const isExpired = computed(() => sessionState.value === 'expired');
const isClosed = computed(() => sessionState.value === 'closed');
const canCapture = computed(() => !isUploading.value && !isExpired.value && !isClosed.value && Boolean(token.value));
const isActionDisabled = computed(() => !canCapture.value);
const actionLabel = computed(() => {
  if (isUploading.value) {
    return 'Upload läuft…';
  }
  if (uploadedTotal.value > 0) {
    return 'Weitere Seite hinzufügen';
  }
  return 'Kamera öffnen';
});
const hintText = computed(() => {
  if (!token.value) {
    return 'Ungültiger Link. Bitte QR-Code am Host neu öffnen.';
  }
  if (isExpired.value) {
    return 'Session abgelaufen. Bitte neuen QR-Code am Host erzeugen.';
  }
  if (isClosed.value) {
    return 'Session geschlossen. Bitte am Host neue Session starten.';
  }
  if (!hasInteracted.value && autoOpenAttempted.value) {
    return 'Falls keine Kamera erscheint: einmal tippen und erneut öffnen.';
  }
  return 'Nach der Aufnahme startet der Upload automatisch.';
});

function resolveApiBaseUrl() {
  const fromProps = String(props.apiBaseUrl || '').trim();
  if (fromProps) {
    return fromProps.replace(/\/$/, '');
  }
  const fromEnv = String(import.meta.env.VITE_API_BASE_URL || '').trim();
  if (fromEnv) {
    return fromEnv.replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin;
  }
  return '';
}

function parseToken() {
  const fromProps = String(props.initialToken || '').trim();
  if (fromProps) {
    return fromProps;
  }
  if (typeof window === 'undefined') {
    return '';
  }
  const query = new URLSearchParams(window.location.search);
  return String(query.get('token') || query.get('t') || '').trim();
}

function formatRemaining(expiresAtIso) {
  if (!expiresAtIso) {
    return '';
  }
  const expires = new Date(expiresAtIso);
  if (Number.isNaN(expires.getTime())) {
    return '';
  }
  const remainingMs = expires.getTime() - Date.now();
  if (remainingMs <= 0) {
    return 'Session abgelaufen.';
  }
  const totalSeconds = Math.floor(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `Läuft ab in ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function refreshExpiry() {
  expiresLabel.value = formatRemaining(expiresAt.value);
}

function setStatus(message, tone = 'neutral') {
  statusMessage.value = String(message || '').trim();
  statusTone.value = tone;
}

function applyStateToStatus(payload) {
  const state = String(payload?.state || '').trim().toLowerCase();
  const step = String(payload?.step || '').trim().toLowerCase();
  sessionState.value = state || 'waiting';

  if (state === 'expired') {
    setStatus('Session abgelaufen. Bitte neuen QR-Code am Host erzeugen.', 'error');
    return;
  }
  if (state === 'error') {
    const detail = String(payload?.errorMessage || '').trim();
    setStatus(detail || 'Verarbeitung fehlgeschlagen.', 'error');
    return;
  }
  if (state === 'processing') {
    if (step === 'pdf') {
      setStatus('PDF wird erzeugt…', 'neutral');
      return;
    }
    if (step === 'detect' || step === 'warp' || step === 'clean') {
      setStatus('Optimierung läuft…', 'neutral');
      return;
    }
    setStatus('Optimierung läuft…', 'neutral');
    return;
  }
  if (state === 'ready' || state === 'closed') {
    setStatus('Upload abgeschlossen. Du kannst weitere Seiten fotografieren.', 'success');
    return;
  }
  if (state === 'receiving') {
    setStatus('Upload empfangen…', 'neutral');
    return;
  }
  setStatus('Bereit zum Fotografieren.', 'neutral');
}

async function refreshStatus() {
  if (!token.value) {
    return;
  }
  try {
    const payload = await getPhoneScanStatus(resolveApiBaseUrl(), token.value);
    uploadedTotal.value = Number(payload?.filesCount || 0);
    expiresAt.value = String(payload?.expiresAt || '');
    refreshExpiry();
    applyStateToStatus(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Status konnte nicht geladen werden.';
    setStatus(message, 'error');
  }
}

function openPicker() {
  if (!canCapture.value) {
    return;
  }
  fileInputRef.value?.click?.();
}

function openPickerFromButton() {
  hasInteracted.value = true;
  openPicker();
}

function onFirstInteraction() {
  if (hasInteracted.value) {
    return;
  }
  hasInteracted.value = true;
  openPicker();
}

function classifyUploadError(message) {
  const normalized = String(message || '').toLowerCase();
  if (normalized.includes('expired') || normalized.includes('abgelaufen')) {
    return 'Session abgelaufen. Bitte neuen QR-Code am Host erzeugen.';
  }
  if (normalized.includes('token')) {
    return 'Upload-Link ist ungültig.';
  }
  if (normalized.includes('network') || normalized.includes('fetch')) {
    return 'Keine Verbindung zum Server.';
  }
  return String(message || 'Upload fehlgeschlagen.');
}

async function onFileInputChange(event) {
  const files = Array.from(event.target?.files || []);
  event.target.value = '';
  if (files.length <= 0) {
    return;
  }
  if (!token.value) {
    setStatus('Upload-Link ist ungültig.', 'error');
    return;
  }

  isUploading.value = true;
  setStatus(`Upload läuft (${files.length} Foto${files.length === 1 ? '' : 's'})…`, 'neutral');
  try {
    const uploadMeta = {
      filterMode: 'clean',
      clientTimestamp: new Date().toISOString(),
      items: files.map((file, index) => ({
        order: index,
        clientTimestamp: new Date().toISOString(),
        filename: String(file?.name || '').trim() || `photo-${index + 1}.jpg`
      }))
    };
    const result = await uploadPhoneScanFiles(resolveApiBaseUrl(), token.value, files, uploadMeta);
    const received = Number(result?.receivedCount || files.length);
    setStatus(`${received} Foto${received === 1 ? '' : 's'} empfangen. Optimierung läuft…`, 'neutral');
    await refreshStatus();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Upload fehlgeschlagen.';
    setStatus(classifyUploadError(message), 'error');
  } finally {
    isUploading.value = false;
  }
}

function tryAutoOpenOnce() {
  if (autoOpenAttempted.value || !canCapture.value) {
    return;
  }
  autoOpenAttempted.value = true;
  window.setTimeout(() => {
    openPicker();
  }, 60);
}

onMounted(async () => {
  token.value = parseToken();
  if (!token.value) {
    setStatus('Ungültiger Scan-Link (Token fehlt).', 'error');
    return;
  }
  await refreshStatus();
  tryAutoOpenOnce();

  pollTimer = window.setInterval(() => {
    void refreshStatus();
  }, 2200);
  countdownTimer = window.setInterval(() => {
    refreshExpiry();
  }, 1000);
});

onBeforeUnmount(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
  if (countdownTimer) {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
  }
});
</script>

<style scoped>
.mobile-scan-capture {
  min-height: 100dvh;
  background:
    radial-gradient(circle at 12% 14%, rgba(134, 239, 172, 0.22), transparent 44%),
    radial-gradient(circle at 90% 4%, rgba(125, 211, 252, 0.26), transparent 40%),
    linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
  padding: clamp(16px, 4vw, 28px);
  display: grid;
  place-items: center;
}

.mobile-scan-capture__card {
  width: min(560px, 100%);
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 24px 44px rgba(15, 23, 42, 0.12);
  padding: clamp(18px, 4vw, 28px);
  display: grid;
  gap: 14px;
}

.mobile-scan-capture__header {
  display: grid;
  gap: 8px;
}

.mobile-scan-capture__header h1 {
  margin: 0;
  font-size: clamp(1.25rem, 4.2vw, 1.6rem);
  line-height: 1.2;
}

.mobile-scan-capture__header p {
  margin: 0;
  color: rgba(15, 23, 42, 0.72);
  line-height: 1.4;
}

.mobile-scan-capture__eyebrow {
  margin: 0;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(15, 23, 42, 0.52);
}

.mobile-scan-capture__input {
  display: none;
}

.mobile-scan-capture__action {
  border: none;
  border-radius: 14px;
  min-height: 50px;
  padding: 0 16px;
  font-size: 0.98rem;
  font-weight: 650;
  color: #ffffff;
  background: linear-gradient(140deg, #0f172a 0%, #1e293b 100%);
}

.mobile-scan-capture__action:disabled {
  opacity: 0.55;
}

.mobile-scan-capture__hint {
  margin: -4px 0 0;
  font-size: 0.82rem;
  color: rgba(15, 23, 42, 0.6);
  line-height: 1.35;
}

.mobile-scan-capture__meta {
  display: grid;
}

.mobile-scan-capture__expires {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(15, 23, 42, 0.6);
}

.mobile-scan-capture__status {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.45;
}

.mobile-scan-capture__status.is-neutral {
  color: rgba(15, 23, 42, 0.78);
}

.mobile-scan-capture__status.is-success {
  color: #166534;
}

.mobile-scan-capture__status.is-warning {
  color: #92400e;
}

.mobile-scan-capture__status.is-error {
  color: #b91c1c;
}

.mobile-scan-capture__uploaded {
  margin: 0;
  font-size: 0.88rem;
  color: rgba(15, 23, 42, 0.68);
}
</style>

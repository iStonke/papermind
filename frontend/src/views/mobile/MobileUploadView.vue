<template>
  <main class="mobile-upload">
    <section class="mobile-upload__card">
      <header class="mobile-upload__header">
        <p class="mobile-upload__eyebrow">PaperMind</p>
        <h1>Live Scan Upload</h1>
        <p>Scanne Dokumente direkt im Browser und sende sie an den wartenden Host.</p>
      </header>

      <button
        type="button"
        class="mobile-upload__action"
        :disabled="scanButtonDisabled"
        @click="openScanner"
      >
        {{ scanButtonLabel }}
      </button>

      <p class="mobile-upload__picker-hint">
        Öffnet den Live-Dokumenten-Scanner (Kamera, Crop, Filter, Mehrseiten).
      </p>

      <div class="mobile-upload__meta">
        <p class="mobile-upload__session">Session {{ sessionId }}</p>
        <p v-if="expiresLabel" class="mobile-upload__expires">{{ expiresLabel }}</p>
      </div>

      <p class="mobile-upload__status" :class="`is-${statusTone}`">{{ statusMessage }}</p>
      <p v-if="uploadedTotal > 0" class="mobile-upload__uploaded">
        Bereits empfangen: {{ uploadedTotal }} Datei{{ uploadedTotal === 1 ? '' : 'en' }}.
      </p>
    </section>

    <WebScanDialog
      v-model="isScannerOpen"
      output-mode="files"
      @files-ready="onScannerFilesReady"
      @pdf-ready="onScannerPdfReady"
    />
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

import WebScanDialog from '../../components/import/WebScanDialog.vue';
import { getMobileUploadStatus, uploadMobileFiles } from '../../api/mobileUpload';

const props = defineProps({
  sessionId: { type: String, required: true },
  initialToken: { type: String, default: '' },
  apiBaseUrl: { type: String, default: '' }
});

const isUploading = ref(false);
const isScannerOpen = ref(false);
const statusMessage = ref('Scanner wird vorbereitet...');
const statusTone = ref('neutral');
const uploadedTotal = ref(0);
const sessionStatus = ref('open');
const expiresAt = ref('');
const expiresLabel = ref('');
const token = ref('');

let statusPollTimer = null;
let countdownTimer = null;

const isExpired = computed(() => sessionStatus.value === 'expired');
const isClosed = computed(() => sessionStatus.value === 'closed');
const hasToken = computed(() => Boolean(String(token.value || '').trim()));
const hasSecureContext = computed(() => (typeof window === 'undefined' ? true : window.isSecureContext === true));
const scanButtonDisabled = computed(
  () => isUploading.value || isExpired.value || isClosed.value || !hasToken.value || !hasSecureContext.value
);
const scanButtonLabel = computed(() => {
  if (isUploading.value) {
    return 'Upload läuft...';
  }
  return uploadedTotal.value > 0 ? 'Weitere Seiten scannen' : 'Dokument scannen';
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
  return String(new URLSearchParams(window.location.search).get('t') || '').trim();
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

function refreshCountdownLabel() {
  expiresLabel.value = formatRemaining(expiresAt.value);
}

function setStatus(message, tone = 'neutral') {
  statusMessage.value = String(message || '').trim();
  statusTone.value = tone;
}

function classifyUploadError(message) {
  const normalized = String(message || '').toLowerCase();
  if (normalized.includes('expired') || normalized.includes('abgelaufen')) {
    return 'Session abgelaufen. Bitte am Host einen neuen QR-Code erzeugen.';
  }
  if (normalized.includes('token')) {
    return 'Upload-Link ist ungültig.';
  }
  if (normalized.includes('failed to fetch') || normalized.includes('network')) {
    return 'Keine Verbindung zum Server.';
  }
  return String(message || 'Upload fehlgeschlagen.');
}

async function refreshStatus({ silent = false } = {}) {
  try {
    const payload = await getMobileUploadStatus(resolveApiBaseUrl(), props.sessionId, {
      token: token.value || undefined
    });
    sessionStatus.value = String(payload?.status || 'open');
    uploadedTotal.value = Number(payload?.filesCount || 0);
    expiresAt.value = String(payload?.expiresAt || '');
    refreshCountdownLabel();

    if (isExpired.value) {
      isScannerOpen.value = false;
      setStatus('Session abgelaufen. Bitte am Host einen neuen QR-Code erzeugen.', 'error');
      return;
    }
    if (isClosed.value) {
      isScannerOpen.value = false;
      setStatus('Session geschlossen. Bitte am Host eine neue Session starten.', 'warning');
      return;
    }
    if (!silent) {
      setStatus('Scanner bereit.', 'neutral');
    }
  } catch (error) {
    if (!silent) {
      const message = error instanceof Error ? error.message : 'Status konnte nicht geladen werden.';
      setStatus(message, 'error');
    }
  }
}

async function uploadScannedFiles(files) {
  const normalizedFiles = Array.from(files || []).filter((entry) => entry instanceof File && entry.size > 0);
  if (normalizedFiles.length <= 0) {
    return;
  }
  if (!hasToken.value) {
    setStatus('Upload-Link ist unvollständig (Token fehlt).', 'error');
    return;
  }

  isUploading.value = true;
  setStatus(`Upload läuft (${normalizedFiles.length} Datei${normalizedFiles.length === 1 ? '' : 'en'})...`, 'neutral');
  try {
    const result = await uploadMobileFiles(resolveApiBaseUrl(), props.sessionId, normalizedFiles, {
      token: token.value
    });
    const uploaded = Number(result?.uploaded || normalizedFiles.length);
    setStatus(`Upload erfolgreich (${uploaded} Datei${uploaded === 1 ? '' : 'en'}).`, 'success');
    await refreshStatus({ silent: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Upload fehlgeschlagen.';
    setStatus(classifyUploadError(message), 'error');
    await refreshStatus({ silent: true });
  } finally {
    isUploading.value = false;
  }
}

async function onScannerFilesReady(payload = {}) {
  const files = Array.isArray(payload?.files) ? payload.files : [];
  await uploadScannedFiles(files);
}

async function onScannerPdfReady(payload = {}) {
  const file = payload?.file;
  if (!(file instanceof File)) {
    return;
  }
  await uploadScannedFiles([file]);
}

function openScanner() {
  if (scanButtonDisabled.value) {
    return;
  }
  isScannerOpen.value = true;
}

onMounted(async () => {
  token.value = parseToken();
  refreshCountdownLabel();
  await refreshStatus({ silent: true });

  if (!hasToken.value) {
    setStatus('Upload-Link ist unvollständig (Token fehlt).', 'error');
    return;
  }
  if (!hasSecureContext.value) {
    setStatus('Kamera benötigt HTTPS (oder localhost). Öffne den QR-Link über eine sichere URL.', 'error');
    return;
  }
  if (isExpired.value) {
    setStatus('Session abgelaufen. Bitte am Host einen neuen QR-Code erzeugen.', 'error');
    return;
  }
  if (isClosed.value) {
    setStatus('Session geschlossen. Bitte am Host neue Session starten.', 'warning');
    return;
  }

  setStatus('Scanner bereit.', 'neutral');
  isScannerOpen.value = true;

  statusPollTimer = window.setInterval(() => {
    void refreshStatus({ silent: true });
  }, 2500);
  countdownTimer = window.setInterval(() => {
    refreshCountdownLabel();
  }, 1000);
});

onBeforeUnmount(() => {
  if (statusPollTimer) {
    window.clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
  if (countdownTimer) {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
  }
});
</script>

<style scoped>
.mobile-upload {
  min-height: 100dvh;
  background:
    radial-gradient(circle at 12% 14%, rgba(134, 239, 172, 0.25), transparent 44%),
    radial-gradient(circle at 90% 4%, rgba(125, 211, 252, 0.26), transparent 40%),
    linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
  padding: clamp(16px, 4vw, 28px);
  display: grid;
  place-items: center;
}

.mobile-upload__card {
  width: min(560px, 100%);
  background: #ffffff;
  border-radius: 24px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 24px 44px rgba(15, 23, 42, 0.12);
  padding: clamp(18px, 4vw, 28px);
  display: grid;
  gap: 14px;
}

.mobile-upload__header {
  display: grid;
  gap: 8px;
}

.mobile-upload__header h1 {
  margin: 0;
  font-size: clamp(1.3rem, 4.2vw, 1.6rem);
  line-height: 1.2;
}

.mobile-upload__header p {
  margin: 0;
  color: rgba(15, 23, 42, 0.72);
  line-height: 1.5;
}

.mobile-upload__eyebrow {
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(15, 23, 42, 0.52);
}

.mobile-upload__action {
  border: none;
  border-radius: 14px;
  min-height: 48px;
  padding: 0 16px;
  font-size: 0.96rem;
  font-weight: 650;
  color: #ffffff;
  background: linear-gradient(140deg, #0f172a 0%, #1e293b 100%);
}

.mobile-upload__action:disabled {
  opacity: 0.56;
}

.mobile-upload__meta {
  display: grid;
  gap: 2px;
}

.mobile-upload__picker-hint {
  margin: -4px 0 0;
  font-size: 0.8rem;
  color: rgba(15, 23, 42, 0.56);
  line-height: 1.35;
}

.mobile-upload__session {
  margin: 0;
  font-size: 0.76rem;
  color: rgba(15, 23, 42, 0.45);
  word-break: break-word;
}

.mobile-upload__expires {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(15, 23, 42, 0.6);
}

.mobile-upload__status {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.45;
}

.mobile-upload__status.is-neutral {
  color: rgba(15, 23, 42, 0.78);
}

.mobile-upload__status.is-success {
  color: #166534;
}

.mobile-upload__status.is-warning {
  color: #92400e;
}

.mobile-upload__status.is-error {
  color: #b91c1c;
}

.mobile-upload__uploaded {
  margin: 0;
  font-size: 0.88rem;
  color: rgba(15, 23, 42, 0.68);
}
</style>

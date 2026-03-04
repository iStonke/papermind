<template>
  <BaseDialog
    v-model="isOpen"
    max-width="760"
    card-class="mobile-scan-qr-dialog"
    body-class="mobile-scan-qr-dialog__body"
    :title="dialogTitle"
    :header-subtitle="dialogSubtitle"
    :show-secondary="false"
    description=""
    @close="stopTimers"
  >
    <div class="mobile-scan-qr">
      <div class="mobile-scan-qr__qr-card">
        <div v-if="qrState === 'loading'" class="mobile-scan-qr__placeholder">
          <v-progress-circular indeterminate size="32" />
          <p>Session wird erstellt...</p>
        </div>
        <div v-else-if="qrState === 'ready'" class="mobile-scan-qr__qr-wrap">
          <img class="mobile-scan-qr__qr" :src="qrDataUrl" alt="QR-Code für iPhone Upload" />
        </div>
        <div v-else class="mobile-scan-qr__qr-error">
          <p class="mobile-scan-qr__qr-error-text">QR-Code konnte nicht erstellt werden.</p>
          <v-btn
            variant="tonal"
            color="primary"
            class="mobile-scan-qr__qr-retry-btn"
            @click="recreateSession"
          >
            Neu erstellen
          </v-btn>
        </div>
      </div>

      <div class="mobile-scan-qr__info-col">
        <div class="mobile-scan-qr__step">
          <p class="mobile-scan-qr__step-title">1. QR-Code scannen</p>
          <p class="mobile-scan-qr__step-text">Öffnet die Upload-Seite auf dem iPhone.</p>
        </div>

        <div class="mobile-scan-qr__step">
          <p class="mobile-scan-qr__step-title">2. Link kopieren</p>
          <p class="mobile-scan-qr__step-text">Link kopieren, falls QR-Code nicht geht.</p>
          <div class="mobile-scan-qr__actions-row">
            <v-btn
              v-if="session?.uploadUrl"
              size="small"
              variant="tonal"
              color="primary"
              class="mobile-scan-qr__copy-btn"
              prepend-icon="mdi-content-copy"
              @click="copyUploadLink"
            >
              Link kopieren
            </v-btn>
          </div>
        </div>

        <div class="mobile-scan-qr__divider" aria-hidden="true" />

        <div class="mobile-scan-qr__step">
          <div class="mobile-scan-qr__section-title">Status</div>
          <div class="mobile-scan-qr__status-row" :class="`is-${statusTone}`">
            <v-progress-circular v-if="statusTone === 'waiting'" indeterminate size="14" width="2" />
            <span class="mobile-scan-qr__status-text">{{ statusMessage }}</span>
            <span v-if="remainingLabel" class="mobile-scan-qr__status-dot">•</span>
            <span v-if="remainingLabel" class="mobile-scan-qr__status-expiry">{{ remainingLabel }}</span>
          </div>
        </div>

        <div class="mobile-scan-qr__recent-zone">
          <div v-if="!hasUploadStarted" class="mobile-scan-qr__waiting-panel">
            <div v-if="localhostHint" class="mobile-scan-qr__waiting-infobox">
              iPhone erreicht localhost nicht. Nutze LAN-IP oder <code>PUBLIC_WEB_BASE_URL</code>.
            </div>
          </div>

          <div v-else class="mobile-scan-qr__uploads-panel">
            <div class="mobile-scan-qr__recent-header">
              <span class="mobile-scan-qr__section-title mobile-scan-qr__section-title--compact">Uploads</span>
              <div class="mobile-scan-qr__recent-meta">
                <span class="mobile-scan-qr__mini-chip mobile-scan-qr__mini-chip--accent">letzte 3</span>
                <span v-if="uploadedTotalCount > 3" class="mobile-scan-qr__mini-chip mobile-scan-qr__mini-chip--muted">
                  +{{ uploadedTotalCount - 3 }}
                </span>
              </div>
            </div>

            <div class="mobile-scan-qr__recent-body mobile-scan-qr__recent-body--with-header">
              <transition-group name="mobile-scan-recent" tag="div" class="mobile-scan-qr__recent-list">
              <div v-for="upload in recentUploads" :key="upload.id" class="mobile-scan-qr__recent-row">
                <span class="mobile-scan-qr__recent-fn">{{ upload.filename }}</span>
              </div>
              </transition-group>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="mobile-scan-qr__actions">
        <v-btn v-if="qrState !== 'error'" variant="text" @click="recreateSession">Neu erstellen</v-btn>
        <span v-else />
        <v-btn color="primary" variant="flat" @click="isOpen = false">Fertig</v-btn>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import QRCode from 'qrcode';

import BaseDialog from '../BaseDialog.vue';
import { createPhoneScanSession, getPhoneScanStatus } from '../../api/phoneScan';
import { mapApiError, useNotifications } from '../../stores/notifications';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  apiBaseUrl: { type: String, default: '' },
  targetStageId: { type: String, default: '' },
  targetStageName: { type: String, default: '' },
  mode: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'sources-received']);

const { notify } = useNotifications();

const isInitializing = ref(false);
const session = ref(null);
const qrDataUrl = ref('');
const qrState = ref('loading');
const remainingLabel = ref('');
const statusMessage = ref('Warte auf Upload...');
const statusTone = ref('waiting');
const recentUploads = ref([]);
const uploadedTotalCount = ref(0);

let pollTimer = null;
let countdownTimer = null;
const seenSourceIds = new Set();

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
});

const resolvedTargetStageId = computed(() => String(props.targetStageId || '').trim() || null);
const receivedCount = computed(() => recentUploads.value.length);
const hasUploadStarted = computed(() => receivedCount.value > 0);
const resolvedMode = computed(() => {
  const normalized = String(props.mode || '').trim().toLowerCase();
  if (normalized === 'stage' || normalized === 'global') {
    return normalized;
  }
  return resolvedTargetStageId.value ? 'stage' : 'global';
});
const dialogTitle = computed(() => (resolvedMode.value === 'stage' ? 'Dokument scannen' : 'Mit iPhone scannen'));
const dialogSubtitle = computed(() => {
  return 'Scanne mit dem iPhone und lade hier hoch.';
});

const localhostHint = computed(() => {
  const uploadUrl = String(session.value?.uploadUrl || '').trim();
  if (!uploadUrl) {
    return false;
  }
  try {
    const hostname = new URL(uploadUrl).hostname.toLowerCase();
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]' || hostname === '::1';
  } catch {
    return false;
  }
});

function stopTimers() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
  if (countdownTimer) {
    window.clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function normalizeUploadFilename(rawValue) {
  const normalized = String(rawValue || '').trim();
  if (!normalized) {
    return 'Unbenanntes Dokument';
  }
  return normalized;
}

function registerRecentUploads(sourceItems = []) {
  const items = Array.isArray(sourceItems) ? sourceItems : [];
  if (items.length === 0) {
    return;
  }

  const created = [];
  for (const source of items) {
    const sourceFileId = String(source?.source_file_id || '').trim();
    if (!sourceFileId) {
      continue;
    }
    const createdAt = Number(new Date(String(source?.created_at || '')).getTime()) || Date.now();
    const stableId = String(source?.upload_id || '').trim() || `${sourceFileId}-${createdAt}`;
    if (recentUploads.value.some((entry) => entry.id === stableId)) {
      continue;
    }
    created.push({
      id: stableId,
      filename: normalizeUploadFilename(source?.original_name),
      receivedAt: createdAt
    });
  }

  if (created.length <= 0) {
    return;
  }

  uploadedTotalCount.value += created.length;
  recentUploads.value.unshift(...created);
  if (recentUploads.value.length > 3) {
    recentUploads.value.splice(3);
  }
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
    return 'Session abgelaufen';
  }
  const totalSeconds = Math.floor(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `Läuft ab in ${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function refreshRemainingLabel() {
  remainingLabel.value = formatRemaining(session.value?.expiresAt);
}

async function renderQrCode(url) {
  qrDataUrl.value = await QRCode.toDataURL(url, {
    errorCorrectionLevel: 'M',
    margin: 1,
    width: 260,
    color: {
      dark: '#0f172a',
      light: '#ffffff'
    }
  });
}

function classifyStatusTone(status) {
  const normalized = String(status || '').trim().toLowerCase();
  if (normalized === 'error' || normalized === 'expired') {
    return 'error';
  }
  if (normalized === 'ready' || normalized === 'closed') {
    return 'success';
  }
  return 'waiting';
}

function extractNewSources(statusPayload) {
  const files = Array.isArray(statusPayload?.files) ? statusPayload.files : [];
  const fresh = [];
  for (const entry of files) {
    const sourceFileId = String(entry?.sourceFileId || '').trim();
    if (!sourceFileId || seenSourceIds.has(sourceFileId)) {
      continue;
    }
    seenSourceIds.add(sourceFileId);
    fresh.push({
      upload_id: String(entry?.id || '').trim(),
      source_file_id: sourceFileId,
      original_name: String(entry?.filename || '').trim() || 'Scan Upload.pdf',
      page_count: Number(entry?.pageCount || 0),
      target_stage_id: String(entry?.targetStageId || '').trim() || null,
      created_at: String(entry?.createdAt || '')
    });
  }
  return fresh.filter((item) => item.page_count > 0);
}

async function pollStatus() {
  if (!session.value?.token) {
    return;
  }
  try {
    const payload = await getPhoneScanStatus(props.apiBaseUrl, session.value.token);
    session.value = {
      ...session.value,
      expiresAt: payload?.expiresAt || session.value.expiresAt
    };
    refreshRemainingLabel();

    const freshSources = extractNewSources(payload);
    if (freshSources.length > 0) {
      registerRecentUploads(freshSources);
      emit('sources-received', {
        sources: freshSources,
        targetStageId: resolvedTargetStageId.value,
        sessionId: String(session.value?.sessionId || '').trim()
      });
    }

    const currentState = String(payload?.state || '').trim().toLowerCase();
    if (currentState === 'expired') {
      statusTone.value = 'error';
      statusMessage.value = 'Session ist abgelaufen. Bitte neu erstellen.';
      stopTimers();
      return;
    }

    statusTone.value = classifyStatusTone(currentState);
    if (currentState === 'receiving') {
      statusMessage.value = 'Upload empfangen…';
      return;
    }
    if (currentState === 'processing') {
      statusMessage.value = String(payload?.step || '').trim() || 'Optimierung läuft…';
      return;
    }
    if (currentState === 'ready' || currentState === 'closed') {
      statusMessage.value = 'PDF bereit.';
      return;
    }
    if (currentState === 'error') {
      statusMessage.value = String(payload?.errorMessage || '').trim() || 'Verarbeitung fehlgeschlagen.';
      return;
    }
    statusMessage.value = 'Warte auf Upload…';
  } catch (error) {
    statusTone.value = 'error';
    statusMessage.value = mapApiError(error, 'Status konnte nicht aktualisiert werden.');
  }
}

async function createSession() {
  stopTimers();
  seenSourceIds.clear();
  recentUploads.value = [];
  uploadedTotalCount.value = 0;
  isInitializing.value = true;
  qrState.value = 'loading';
  statusTone.value = 'waiting';
  statusMessage.value = 'Warte auf Upload...';
  qrDataUrl.value = '';

  try {
    const payload = await createPhoneScanSession(props.apiBaseUrl, {
      maxFiles: 20,
      stageId: resolvedTargetStageId.value
    });
    session.value = payload;
    await renderQrCode(payload.uploadUrl);
    qrState.value = 'ready';
    refreshRemainingLabel();
    await pollStatus();
    pollTimer = window.setInterval(() => {
      void pollStatus();
    }, 1500);
    countdownTimer = window.setInterval(() => {
      refreshRemainingLabel();
    }, 1000);
  } catch (error) {
    qrState.value = 'error';
    statusTone.value = 'error';
    statusMessage.value = mapApiError(error, 'Session konnte nicht erstellt werden.');
  } finally {
    isInitializing.value = false;
  }
}

async function recreateSession() {
  await createSession();
}

async function copyUploadLink() {
  const uploadUrl = String(session.value?.uploadUrl || '').trim();
  if (!uploadUrl) {
    return;
  }
  try {
    await navigator.clipboard.writeText(uploadUrl);
    notify({ type: 'success', message: 'Link kopiert.' });
  } catch {
    notify({ type: 'warning', message: 'Link konnte nicht kopiert werden.' });
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void createSession();
      return;
    }
    stopTimers();
  }
);

onBeforeUnmount(() => {
  stopTimers();
});
</script>

<style scoped>
.mobile-scan-qr {
  --msq-panel-bg: rgb(var(--v-theme-surface-2, var(--v-theme-surface)));
  --msq-panel-border: var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  --msq-qr-shell-bg: linear-gradient(
    180deg,
    rgba(var(--v-theme-on-surface), 0.05) 0%,
    rgba(var(--v-theme-on-surface), 0.025) 100%
  );
  --msq-text-main: rgba(var(--v-theme-on-surface), 0.9);
  --msq-text-muted: rgba(var(--v-theme-on-surface), 0.72);
  --msq-text-soft: rgba(var(--v-theme-on-surface), 0.62);
  --msq-code-bg: rgba(var(--v-theme-on-surface), 0.05);
  --msq-code-border: rgba(var(--v-theme-on-surface), 0.14);
  --msq-status-waiting: rgba(var(--v-theme-on-surface), 0.86);
  --msq-status-success: rgba(var(--v-theme-success, 34, 197, 94), 1);
  --msq-status-error: rgba(var(--v-theme-error, 239, 68, 68), 1);
  --msq-tip-text: rgba(var(--v-theme-on-surface), 0.8);
  --msq-tip-accent: rgba(var(--v-theme-info, var(--v-theme-primary)), 0.9);
  --msq-tip-bg: rgba(var(--v-theme-info, var(--v-theme-primary)), 0.1);

  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 20px;
  align-items: stretch;
  color: var(--msq-text-main);
}

.mobile-scan-qr__qr-card {
  min-height: 336px;
  border-radius: 22px;
  border: 1px solid var(--msq-panel-border);
  background: var(--msq-qr-shell-bg);
  display: grid;
  place-items: center;
  padding: 18px;
}

.mobile-scan-qr__qr-wrap {
  width: 100%;
  display: grid;
  place-items: center;
}

.mobile-scan-qr__qr {
  width: min(100%, 320px);
  height: auto;
  border-radius: 15px;
  background: #fff;
  border: 1px solid var(--msq-code-border);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.14);
  padding: 12px;
}

.mobile-scan-qr__placeholder {
  display: grid;
  justify-items: center;
  gap: 10px;
  text-align: center;
  color: var(--msq-text-muted);
}

.mobile-scan-qr__placeholder--error {
  color: var(--msq-status-error);
}

.mobile-scan-qr__qr-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
}

.mobile-scan-qr__qr-error-text {
  margin: 0;
  color: var(--msq-status-error);
  font-weight: 500;
  font-size: 0.95rem;
}

.mobile-scan-qr__qr-retry-btn {
  min-width: 160px;
  text-transform: none;
}

.mobile-scan-qr__info-col {
  display: grid;
  gap: 10px;
  align-content: start;
  padding-top: 2px;
}

.mobile-scan-qr__step {
  display: grid;
  gap: 4px;
  margin-bottom: 8px;
}

.mobile-scan-qr__step:last-of-type {
  margin-bottom: 0;
}

.mobile-scan-qr__step-title {
  margin: 0;
  font-size: 0.97rem;
  line-height: 1.25;
  font-weight: 600;
  color: var(--msq-text-main);
}

.mobile-scan-qr__section-title {
  margin: 0 0 6px;
  font-size: 0.81rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--msq-text-soft);
  opacity: 0.75;
  line-height: 1.2;
}

.mobile-scan-qr__section-title--compact {
  margin: 0;
}

.mobile-scan-qr__step-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.35;
  color: var(--msq-text-muted);
}

.mobile-scan-qr__actions-row {
  display: flex;
  justify-content: flex-start;
  margin-top: 2px;
}

.mobile-scan-qr__divider {
  height: 1px;
  width: 100%;
  background: var(--pm-divider-soft, rgba(15, 23, 42, 0.08));
  margin: 2px 0 8px;
}

.mobile-scan-qr__copy-btn {
  text-transform: none;
}

.mobile-scan-qr__copy-btn :deep(.v-btn__content) {
  text-transform: none;
  letter-spacing: 0;
}

.mobile-scan-qr__status-row {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.82rem;
  line-height: 1.35;
  color: var(--msq-text-soft);
  margin-bottom: 12px;
}

.mobile-scan-qr__status-row.is-waiting {
  color: var(--msq-status-waiting);
}

.mobile-scan-qr__status-row.is-success {
  color: var(--msq-status-success);
}

.mobile-scan-qr__status-row.is-error {
  color: var(--msq-status-error);
}

.mobile-scan-qr__status-dot {
  opacity: 0.8;
}

.mobile-scan-qr__status-expiry {
  color: var(--msq-text-soft);
}

.mobile-scan-qr__recent-zone {
  margin-top: 0;
  height: 106px;
  overflow: hidden;
  position: relative;
}

.mobile-scan-qr__waiting-panel,
.mobile-scan-qr__uploads-panel {
  height: 100%;
  overflow: hidden;
}

.mobile-scan-qr__waiting-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-scan-qr__recent-header {
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  margin-bottom: 8px;
}

.mobile-scan-qr__recent-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.mobile-scan-qr__mini-chip {
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.86;
  color: var(--msq-text-soft);
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.mobile-scan-qr__mini-chip--accent {
  color: rgba(var(--v-theme-primary), 0.98);
  background: rgba(var(--v-theme-primary), 0.14);
  border-color: rgba(var(--v-theme-primary), 0.32);
  opacity: 0.92;
}

.mobile-scan-qr__mini-chip--muted {
  opacity: 0.76;
}

.mobile-scan-qr__recent-body {
  height: 100%;
  overflow: hidden;
}

.mobile-scan-qr__recent-body--with-header {
  height: calc(100% - 26px);
  overflow: hidden;
}

.mobile-scan-qr__waiting-infobox {
  max-height: 74px;
  overflow: hidden;
  border-left: 3px solid var(--msq-tip-accent);
  border-radius: 8px;
  background: var(--msq-tip-bg);
  padding: 10px 12px;
  font-size: 0.76rem;
  line-height: 1.35;
  color: var(--msq-tip-text);
  word-break: break-word;
  overflow-wrap: anywhere;
  hyphens: auto;
}

.mobile-scan-qr__waiting-infobox code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9em;
  opacity: 0.92;
  word-break: break-all;
}

.mobile-scan-qr__recent-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.mobile-scan-qr__recent-row {
  position: relative;
  height: 28px;
  padding: 4px 10px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.045);
}

.mobile-scan-qr__recent-fn {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.8rem;
  line-height: 1.2;
  color: var(--msq-text-main);
}

.mobile-scan-recent-enter-active,
.mobile-scan-recent-leave-active {
  transition: transform 200ms ease, opacity 200ms ease;
}

.mobile-scan-recent-enter-from {
  transform: translateY(-6px);
  opacity: 0;
}

.mobile-scan-recent-enter-to {
  transform: translateY(0);
  opacity: 1;
}

.mobile-scan-recent-leave-from {
  transform: translateY(0);
  opacity: 1;
}

.mobile-scan-recent-leave-to {
  transform: translateY(6px);
  opacity: 0;
}

.mobile-scan-recent-move {
  transition: transform 200ms ease, opacity 200ms ease;
}

.mobile-scan-recent-leave-active {
  position: absolute;
  width: 100%;
}

.mobile-scan-qr__actions {
  display: flex;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  margin-top: 2px;
  width: 100%;
}

:deep(.mobile-scan-qr-dialog .pm-dialog__header) {
  padding: 12px 16px;
}

:deep(.mobile-scan-qr-dialog .pm-dialog__subtitle) {
  margin-top: 1px;
  font-size: 0.82rem;
  line-height: 1.25;
}

:deep(.mobile-scan-qr-dialog .pm-dialog__content) {
  background: var(--msq-panel-bg);
  padding: 20px 20px 16px;
}

:deep(.mobile-scan-qr-dialog .pm-dialog__header),
:deep(.mobile-scan-qr-dialog .pm-dialog__footer) {
  background: var(--msq-panel-bg);
}

:deep(.mobile-scan-qr-dialog .pm-dialog__footer) {
  padding: 14px 16px;
}

@media (max-width: 900px) {
  .mobile-scan-qr {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .mobile-scan-qr__qr-card {
    min-height: 290px;
  }
}
</style>

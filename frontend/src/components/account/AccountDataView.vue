<template>
  <div class="data">
    <!-- Speicherplatz-Übersicht -->
    <section class="data__block">
      <div class="pm-account-subhead">Speicherplatz</div>

      <div v-if="storageLoading" class="data__state">
        <v-progress-circular indeterminate size="20" width="2" />
        <span>Belegung wird berechnet …</span>
      </div>
      <div v-else-if="storageError" class="data__state data__state--error">
        {{ storageError }}
      </div>
      <template v-else-if="storage">
        <div class="data__summary">
          <div class="data__total">
            <span class="data__total-value">{{ formatBytes(storage.total_bytes) }}</span>
            <span class="data__total-label">
              in {{ storage.document_count }} {{ storage.document_count === 1 ? 'Dokument' : 'Dokumenten' }}
            </span>
          </div>
        </div>

        <div v-if="storage.total_bytes > 0" class="data__bar" aria-hidden="true">
          <span
            v-for="row in roleRows"
            :key="row.key"
            class="data__bar-seg"
            :style="{ width: `${row.percent}%`, background: row.color }"
          />
        </div>

        <div class="data__roles">
          <div v-for="row in roleRows" :key="row.key" class="data__role">
            <span class="data__role-dot" :style="{ background: row.color }" />
            <span class="data__role-label">{{ row.label }}</span>
            <span class="data__role-size">{{ formatBytes(row.bytes) }}</span>
          </div>
          <div v-if="roleRows.length === 0" class="data__empty">Noch keine gespeicherten Dateien.</div>
        </div>
      </template>
    </section>

    <v-divider class="pm-account-divider" />

    <!-- Daten exportieren -->
    <section class="data__block">
      <div class="pm-account-subhead">Meine Daten exportieren</div>
      <p class="data__hint">
        Lädt ein ZIP-Archiv mit den durchsuchbaren PDF-Fassungen aller eigenen Dokumente
        sowie einer <code>metadaten.json</code> herunter. Bei vielen Dokumenten kann die
        Vorbereitung einen Moment dauern.
      </p>
      <div class="data__actions">
        <v-btn
          variant="tonal"
          color="primary"
          class="data__btn"
          prepend-icon="mdi-download-outline"
          :loading="exporting"
          @click="downloadExport"
        >
          Export herunterladen
        </v-btn>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';

import { fetchStorageUsage, personalExportUrl } from '../../api/auth.js';
import { useAuthStore } from '../../stores/auth.js';
import { notifyError, useNotifications } from '../../stores/notifications';

const auth = useAuthStore();
const { notify } = useNotifications();

const ROLE_META = {
  original: { label: 'Originaldateien', color: '#3b82a6' },
  ocr: { label: 'Durchsuchbare PDFs (OCR)', color: '#0f8a94' },
  preview_pdf: { label: 'Vorschau-PDFs', color: '#7d9aa0' },
  thumbnail: { label: 'Vorschaubilder', color: '#b0bfc2' },
};
const ROLE_ORDER = ['original', 'ocr', 'preview_pdf', 'thumbnail'];

const storage = ref(null);
const storageLoading = ref(false);
const storageError = ref('');

const exporting = ref(false);

const roleRows = computed(() => {
  if (!storage.value) return [];
  const total = storage.value.total_bytes || 0;
  const byRole = storage.value.by_role || {};
  return ROLE_ORDER
    .filter((key) => byRole[key] && byRole[key].bytes > 0)
    .map((key) => {
      const bytes = byRole[key].bytes;
      return {
        key,
        label: ROLE_META[key]?.label || key,
        color: ROLE_META[key]?.color || '#999',
        bytes,
        percent: total > 0 ? Math.max((bytes / total) * 100, 1) : 0,
      };
    });
});

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(size >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

async function loadStorage() {
  storageLoading.value = true;
  storageError.value = '';
  try {
    storage.value = await fetchStorageUsage();
  } catch (err) {
    storageError.value = err?.message || 'Belegung konnte nicht geladen werden.';
  } finally {
    storageLoading.value = false;
  }
}

async function downloadExport() {
  exporting.value = true;
  try {
    await auth.refreshFileToken();
    const link = document.createElement('a');
    link.href = personalExportUrl();
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    notify({ type: 'success', message: 'Export wird vorbereitet und heruntergeladen …' });
  } catch (err) {
    notifyError(err, 'Export konnte nicht gestartet werden.');
  } finally {
    window.setTimeout(() => {
      exporting.value = false;
    }, 1500);
  }
}

onMounted(loadStorage);
</script>

<style scoped>
.data {
  max-width: 460px;
  margin-inline: 0;
}
.data__block + .data__block {
  margin-top: 0;
}
.data__state {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
  padding: 4px 0;
}
.data__state--error {
  color: rgb(var(--v-theme-error));
}
.data__summary {
  margin-bottom: 12px;
}
.data__total {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.data__total-value {
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.data__total-label {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.data__bar {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.06);
  margin-bottom: 12px;
}
.data__bar-seg {
  height: 100%;
}
.data__roles {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.data__role {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.82rem;
}
.data__role-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex: 0 0 auto;
}
.data__role-label {
  flex: 1 1 auto;
  color: rgba(var(--v-theme-on-surface), 0.75);
}
.data__role-size {
  font-weight: 500;
  color: rgb(var(--v-theme-on-surface));
}
.data__empty {
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.data__hint {
  margin: 0 0 14px;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.data__hint code {
  font-size: 0.78rem;
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(var(--v-theme-on-surface), 0.07);
}
.data__actions {
  display: flex;
}
.data__btn {
  text-transform: none;
  letter-spacing: normal;
  font-weight: 600;
  border-radius: 10px;
}
.data__note {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.82rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.7);
  background: rgba(var(--v-theme-on-surface), 0.045);
  border-radius: 10px;
  padding: 12px 14px;
}
.data__note .v-icon {
  color: rgb(var(--v-theme-primary));
  flex: 0 0 auto;
  margin-top: 1px;
}
.data__dialog-copy {
  margin: 0 0 16px;
  font-size: 0.9rem;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.78);
}
</style>

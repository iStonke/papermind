<template>
  <v-menu v-if="hasActivity" v-model="menuOpen" location="bottom end" :close-on-content-click="false">
    <template #activator="{ props }">
      <v-btn
        v-bind="props"
        icon
        variant="text"
        size="small"
        class="activity-indicator-btn"
        :aria-label="ariaLabel"
        :title="ariaLabel"
      >
        <v-badge
          :model-value="badgeCount > 0"
          :content="badgeCount"
          :color="badgeColor"
          max="9"
          offset-x="0"
          offset-y="0"
          class="activity-indicator-badge"
        >
          <v-icon v-if="isActive" size="22">mdi-progress-clock</v-icon>
          <v-icon v-else size="22">mdi-alert-circle-outline</v-icon>
        </v-badge>
      </v-btn>
    </template>

    <v-card min-width="320" max-width="440" class="activity-card">
      <div class="activity-card__header">
        <span>Aktivität</span>
        <span class="activity-card__sub">{{ headerSub }}</span>
      </div>
      <v-divider />

      <div v-if="ocrPending > 0" class="activity-ocr">
        <div class="activity-ocr__label">Dokumente werden durchsuchbar gemacht</div>
        <v-progress-linear :model-value="ocrPercent" height="6" rounded color="primary" class="activity-ocr__bar" />
        <div class="activity-ocr__count">
          {{ ocrBacklog.done }} / {{ ocrBacklog.total }} fertig<span v-if="ocrBacklog.failed"> · {{ ocrBacklog.failed }} ohne Texterkennung</span>
        </div>
      </div>
      <v-divider v-if="ocrPending > 0" />

      <div v-if="groups.length === 0 && ocrPending === 0 && !hasBackupFail" class="activity-empty">
        Keine laufenden Prozesse.
      </div>

      <v-list v-else density="compact" class="activity-list">
        <v-list-item
          v-if="hasBackupFail"
          class="activity-item activity-item--clickable"
          @click="openBackup"
        >
          <template #prepend>
            <v-icon size="16" class="activity-item__icon" color="error">mdi-alert-circle-outline</v-icon>
          </template>
          <v-list-item-title class="activity-item__title">Backup auf NAS fehlgeschlagen</v-list-item-title>
          <v-list-item-subtitle class="activity-item__types">
            In den Einstellungen öffnen
          </v-list-item-subtitle>
        </v-list-item>

        <v-list-item v-for="group in groups" :key="group.documentId" class="activity-item">
          <template #prepend>
            <!-- Für laufende/eingereihte Aktivitäten immer einen Spinner zeigen;
                 nur fehlgeschlagene behalten das Fehler-Icon. -->
            <v-progress-circular
              v-if="group.status !== 'failed'"
              indeterminate
              size="16"
              width="2"
              color="primary"
              class="activity-item__icon"
            />
            <v-icon v-else size="16" class="activity-item__icon" color="error">
              mdi-alert-circle-outline
            </v-icon>
          </template>

          <v-list-item-title class="activity-item__title">
            {{ group.documentTitle }}
          </v-list-item-title>

          <v-list-item-subtitle v-if="group.status === 'failed' && group.errorMessage" class="activity-item__error">
            {{ group.errorMessage }}
          </v-list-item-subtitle>
          <v-list-item-subtitle v-else class="activity-item__types">
            {{ group.typesLabel }}
          </v-list-item-subtitle>

          <template v-if="group.status === 'failed'" #append>
            <v-btn
              icon
              variant="text"
              size="x-small"
              class="activity-item__dismiss"
              :disabled="isDismissing"
              title="Fehler entfernen"
              aria-label="Fehler entfernen"
              @click.stop="dismissGroup(group)"
            >
              <v-icon size="16">mdi-close</v-icon>
            </v-btn>
          </template>
        </v-list-item>
      </v-list>

      <template v-if="failedGroups.length > 0">
        <v-divider />
        <div class="activity-footer">
          <v-btn
            variant="text"
            size="small"
            color="error"
            block
            :disabled="isDismissing"
            @click="dismissAllFailed"
          >
            Alle Fehler entfernen
          </v-btn>
        </div>
      </template>
    </v-card>
  </v-menu>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getJobActivity, dismissJob, dismissFailedJobs } from '../api/jobs.js';

const emit = defineEmits(['open-backup']);

const POLL_MS = 4000;
const BURST_MS = 1500;   // schnelleres Polling-Intervall im Schub
const BURST_TICKS = 8;   // Anzahl der Schub-Durchläufe (~12 s)
const TYPE_LABELS = {
  OCR: 'Texterkennung',
  INDEX: 'Indexierung',
  EMBED: 'Embedding',
  TAG: 'Auto-Tagging'
};

const jobs = ref([]);
const ocrBacklog = ref({ total: 0, done: 0, pending: 0, failed: 0 });
const backupFail = ref(null);
const menuOpen = ref(false);
const isDismissing = ref(false);
let timer = null;
let burstTimer = null;

const STATUS_RANK = { running: 0, queued: 1, failed: 2 };

function typeLabel(type) {
  return TYPE_LABELS[type] || type;
}

// Alle Jobs eines Dokuments zu EINEM Eintrag zusammenfassen.
const groups = computed(() => {
  const byDoc = new Map();
  for (const job of jobs.value) {
    const key = job.document_id;
    if (!byDoc.has(key)) {
      byDoc.set(key, { documentId: key, documentTitle: job.document_title || 'Ohne Titel', jobs: [] });
    }
    byDoc.get(key).jobs.push(job);
  }
  const result = [];
  for (const entry of byDoc.values()) {
    const list = entry.jobs;
    let status = 'failed';
    if (list.some((j) => j.status === 'running')) status = 'running';
    else if (list.some((j) => j.status === 'queued')) status = 'queued';
    const types = [...new Set(list.map((j) => j.type))];
    const failedJob = list.find((j) => j.status === 'failed');
    result.push({
      documentId: entry.documentId,
      documentTitle: entry.documentTitle,
      status,
      typesLabel: types.map(typeLabel).join(' · '),
      errorMessage: status === 'failed' ? (failedJob?.error_message || null) : null,
      jobIds: list.map((j) => j.id).filter(Boolean)
    });
  }
  result.sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status]);
  return result;
});

const activeGroups = computed(() => groups.value.filter((g) => g.status === 'running' || g.status === 'queued'));
const failedGroups = computed(() => groups.value.filter((g) => g.status === 'failed'));
// Gesamtfortschritt der Volltext-Erkennung (Dokument-Ebene), sichtbar auch in den
// Pausen zwischen den OCR-Häppchen.
const ocrPending = computed(() => Number(ocrBacklog.value?.pending || 0));
const ocrPercent = computed(() => {
  const total = Number(ocrBacklog.value?.total || 0);
  if (total <= 0) return 0;
  return Math.round((Number(ocrBacklog.value?.done || 0) / total) * 100);
});
const hasBackupFail = computed(() => backupFail.value?.status === 'failed');
const isActive = computed(() => activeGroups.value.length > 0 || ocrPending.value > 0);
// Fehlgeschlagene Dokument-Jobs plus ein evtl. fehlgeschlagenes Backup.
const failedCount = computed(() => failedGroups.value.length + (hasBackupFail.value ? 1 : 0));
const hasFailed = computed(() => failedCount.value > 0);
// Indikator anzeigen, wenn Jobs laufen, Dokumente auf Volltext warten ODER ein Backup fehlschlug.
const hasActivity = computed(() => groups.value.length > 0 || ocrPending.value > 0 || hasBackupFail.value);
const badgeCount = computed(() =>
  isActive.value ? activeGroups.value.length : (hasFailed.value ? failedCount.value : 0)
);
const badgeColor = computed(() => (isActive.value ? 'primary' : 'error'));

const ariaLabel = computed(() => {
  if (isActive.value) return `${activeGroups.value.length} Dokument(e) in Bearbeitung`;
  if (hasFailed.value) return `${failedCount.value} fehlgeschlagen`;
  return 'Keine laufenden Prozesse';
});

const headerSub = computed(() => {
  const parts = [];
  if (activeGroups.value.length) parts.push(`${activeGroups.value.length} in Bearbeitung`);
  if (failedCount.value) parts.push(`${failedCount.value} fehlgeschlagen`);
  return parts.join(' · ') || (ocrPending.value > 0 ? 'läuft im Hintergrund' : 'im Leerlauf');
});

function openBackup() {
  menuOpen.value = false;
  emit('open-backup');
}

async function refresh() {
  try {
    const data = await getJobActivity();
    jobs.value = Array.isArray(data?.jobs) ? data.jobs : [];
    ocrBacklog.value = data?.ocr_backlog ?? { total: 0, done: 0, pending: 0, failed: 0 };
    backupFail.value = data?.backup?.status === 'failed' ? data.backup : null;
  } catch {
    // Aktivität ist optional – Fehler beim Polling nicht stören lassen.
  }
}

// Einen fehlgeschlagenen Eintrag aus der Anzeige entfernen (Job-Zeilen löschen).
async function dismissGroup(group) {
  if (isDismissing.value) return;
  isDismissing.value = true;
  try {
    for (const jobId of group?.jobIds || []) {
      await dismissJob(jobId);
    }
    const removed = new Set(group?.jobIds || []);
    jobs.value = jobs.value.filter((j) => !removed.has(j.id));
    await refresh();
  } catch {
    // ignorieren – das Polling korrigiert die Anzeige
  } finally {
    isDismissing.value = false;
  }
}

// Alle fehlgeschlagenen Jobs auf einmal entfernen.
async function dismissAllFailed() {
  if (isDismissing.value) return;
  isDismissing.value = true;
  try {
    await dismissFailedJobs();
    jobs.value = jobs.value.filter((j) => j.status !== 'failed');
    await refresh();
  } catch {
    // ignorieren
  } finally {
    isDismissing.value = false;
  }
}

// Sofort aktualisieren + kurzer Schub schnelleren Pollings. Wird z. B. nach einem
// Import aufgerufen, damit die frisch eingereihten, oft <1 s kurzen Jobs sicher
// erscheinen (Worker-Intervall 3 s) – sonst verpasst das 4-s-Polling sie.
function poke() {
  refresh();
  if (burstTimer) window.clearInterval(burstTimer);
  let ticks = 0;
  burstTimer = window.setInterval(() => {
    refresh();
    ticks += 1;
    if (ticks >= BURST_TICKS) {
      window.clearInterval(burstTimer);
      burstTimer = null;
    }
  }, BURST_MS);
}

defineExpose({ refresh: poke });

// Beim Öffnen sofort aktualisieren (nicht aufs nächste Polling warten).
watch(menuOpen, (open) => {
  if (open) refresh();
});

// Menü automatisch schließen, sobald keine Aktivitäten mehr da sind.
watch(hasActivity, (active) => {
  if (menuOpen.value && !active) {
    menuOpen.value = false;
  }
});

onMounted(() => {
  refresh();
  timer = window.setInterval(refresh, POLL_MS);
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
  if (burstTimer) window.clearInterval(burstTimer);
});
</script>

<style scoped>
.activity-indicator-btn {
  --activity-badge-size: 13px;
}

.activity-indicator-badge :deep(.v-badge__badge) {
  min-width: var(--activity-badge-size);
  height: var(--activity-badge-size);
  padding: 0 3px;
  border-radius: 999px;
  font-size: 0.58rem;
  font-weight: 700;
  line-height: var(--activity-badge-size);
}

.activity-card {
  /* gleicher Hintergrund wie das Benutzermenü (account-menu) */
  background: rgb(var(--v-theme-card)) !important;
}
.activity-card__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 14px;
  font-weight: 600;
}
.activity-card__sub {
  font-size: 0.72rem;
  font-weight: 400;
  opacity: 0.7;
}
.activity-empty {
  padding: 18px 14px;
  font-size: 0.85rem;
  opacity: 0.7;
  text-align: center;
}
.activity-ocr {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.activity-ocr__label {
  font-size: 0.82rem;
}
.activity-ocr__count {
  font-size: 0.72rem;
  opacity: 0.7;
}
.activity-list {
  max-height: 340px;
  overflow-y: auto;
}
/* Icon-Spalte für alle Aktivitäts-Items identisch, damit laufende (Spinner)
   und fehlgeschlagene (Fehler-Icon) Einträge bündig in einer Flucht stehen.
   Vuetifys variablen Prepend-Spacer dafür neutralisieren. */
.activity-item :deep(.v-list-item__prepend) {
  margin-inline-end: 8px;
}
.activity-item :deep(.v-list-item__spacer) {
  display: none;
}
.activity-item__icon {
  margin-right: 0;
}
.activity-item__doc {
  opacity: 0.7;
  font-weight: 400;
}
.activity-item__error {
  color: rgb(var(--v-theme-error));
  white-space: normal;
}
.activity-item__dismiss {
  opacity: 0.6;
}
.activity-item__dismiss:hover {
  opacity: 1;
}
.activity-footer {
  padding: 4px 8px 8px;
}
.activity-item--clickable {
  cursor: pointer;
}
.activity-item--clickable:hover {
  background: rgba(var(--v-theme-error), 0.06);
}
</style>

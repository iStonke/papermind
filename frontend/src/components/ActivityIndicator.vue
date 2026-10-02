<template>
  <v-menu
    v-if="hasVisibleActivity"
    v-model="menuOpen"
    :location="presentation === 'menu-item' ? 'right end' : 'top end'"
    :close-on-content-click="false"
    :theme="theme.global.name.value"
  >
    <template #activator="{ props }">
      <v-list-item
        v-if="presentation === 'menu-item'"
        v-bind="props"
        class="activity-indicator-menu-item"
        title="Aktivität"
        :subtitle="ariaLabel"
      >
        <template #prepend>
          <v-icon v-if="isActive" size="20">mdi-progress-clock</v-icon>
          <v-icon v-else-if="hasVisibleActivity" size="20">mdi-pause-circle-outline</v-icon>
          <v-icon v-else-if="readyAudioExports.length" size="20" color="success">mdi-download-circle-outline</v-icon>
          <v-icon v-else-if="hasFailed" size="20" color="error">mdi-alert-circle-outline</v-icon>
          <v-icon v-else size="20">mdi-check-circle-outline</v-icon>
        </template>
        <template #append>
          <v-badge
            inline
            :model-value="badgeCount > 0"
            :content="badgeCount"
            :color="badgeColor"
            max="9"
            class="activity-indicator-menu-badge"
          />
          <v-icon size="16">mdi-chevron-right</v-icon>
        </template>
      </v-list-item>
      <v-btn
        v-else
        v-bind="props"
        icon
        variant="text"
        size="small"
        :class="['activity-indicator-btn', buttonClass]"
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
          <v-icon v-else-if="hasVisibleActivity" size="22">mdi-pause-circle-outline</v-icon>
          <v-icon v-else-if="readyAudioExports.length" size="22" color="success">mdi-download-circle-outline</v-icon>
          <v-icon v-else-if="hasFailed" size="22">mdi-alert-circle-outline</v-icon>
          <v-icon v-else size="22">mdi-check-circle-outline</v-icon>
        </v-badge>
      </v-btn>
    </template>

    <v-card min-width="320" max-width="440" class="activity-card">
      <div class="activity-card__header">
        <span>Aktivität</span>
        <div class="activity-card__header-actions">
          <span class="activity-card__sub">{{ headerSub }}</span>
          <v-btn icon variant="text" size="x-small" :loading="refreshing" title="Aktualisieren" aria-label="Aktivität aktualisieren" @click="refresh"><v-icon size="18">mdi-refresh</v-icon></v-btn>
        </div>
      </div>
      <v-divider />

      <div v-if="actionError" class="activity-feedback" role="alert">{{ actionError }}</div>
      <div class="activity-filters">
        <v-btn v-for="filter in filters" :key="filter.value" size="small" :variant="activeFilter === filter.value ? 'tonal' : 'text'" :aria-pressed="activeFilter === filter.value" @click="activeFilter = filter.value">{{ filter.label }}</v-btn>
      </div>
      <div v-if="ocrPending > 0" class="activity-ocr">
        <div class="activity-ocr__label">Dokumente werden durchsuchbar gemacht</div>
        <v-progress-linear :model-value="ocrPercent" height="6" rounded color="primary" class="activity-ocr__bar" />
        <div class="activity-ocr__count">
          {{ ocrBacklog.done }} / {{ ocrBacklog.total }} fertig<span v-if="ocrBacklog.failed"> · {{ ocrBacklog.failed }} ohne Texterkennung</span>
        </div>
      </div>
      <v-divider v-if="ocrPending > 0" />

      <div v-if="visibleGroups.length === 0 && visibleAudioExports.length === 0 && visibleBackground.length === 0 && ocrPending === 0 && !hasBackupFail" class="activity-empty">
        {{ activeFilter === 'all' ? 'Alles erledigt.' : 'Keine passenden Vorgänge.' }}
      </div>

      <v-list v-else density="compact" class="activity-list">
        <v-list-item v-for="job in visibleBackground" :key="`${job.kind}-${job.id}`" class="activity-item">
          <template #prepend><v-progress-circular v-if="['queued', 'running'].includes(job.status)" indeterminate size="18" width="2" color="primary" /><v-icon v-else size="18">{{ job.status === 'paused' ? 'mdi-pause-circle-outline' : 'mdi-stop' }}</v-icon></template>
          <v-list-item-title>{{ job.title }}</v-list-item-title>
          <v-list-item-subtitle>{{ job.error_message || job.phase || ({ queued: 'Wartet', running: 'In Bearbeitung', paused: 'Pausiert', cancelled: 'Beendet', failed: 'Fehlgeschlagen' }[job.status]) }}<span v-if="job.progress != null"> · {{ job.progress }} %</span></v-list-item-subtitle>
          <template #append><div class="activity-item__actions">
            <v-btn v-if="job.kind === 'wiki' && ['queued', 'running', 'paused'].includes(job.status)" icon variant="text" size="x-small" :disabled="backgroundBusy.has(job.id)" :aria-label="job.status === 'paused' ? 'Wissensaufbau fortsetzen' : 'Wissensaufbau pausieren'" :title="job.status === 'paused' ? 'Fortsetzen' : 'Pausieren'" @click="controlBackground(job, job.status === 'paused' ? 'resume' : 'pause')"><v-icon size="17">{{ job.status === 'paused' ? 'mdi-play' : 'mdi-pause' }}</v-icon></v-btn>
            <v-btn icon variant="text" size="x-small" :disabled="backgroundBusy.has(job.id)" title="Neu starten" :aria-label="`${job.title} neu starten`" @click="controlBackground(job, 'restart')"><v-icon size="17">mdi-refresh</v-icon></v-btn>
            <v-btn v-if="['backup', 'preanalysis', 'cleanup'].includes(job.kind) && ['failed', 'cancelled'].includes(job.status)" icon variant="text" size="x-small" :disabled="backgroundBusy.has(job.id)" title="Eintrag entfernen" :aria-label="`${job.title} entfernen`" @click="controlBackground(job, 'dismiss')"><v-icon size="16">mdi-close</v-icon></v-btn>
            <v-btn v-if="['queued', 'running', 'paused'].includes(job.status)" icon variant="text" size="x-small" :disabled="backgroundBusy.has(job.id)" title="Beenden" :aria-label="`${job.title} beenden`" @click="controlBackground(job, 'cancel')"><v-icon size="17">mdi-stop</v-icon></v-btn>
          </div></template>
        </v-list-item>
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

        <v-list-item v-for="job in visibleAudioExports" :key="`audio-${job.id}`" class="activity-item">
          <template #prepend>
            <v-progress-circular
              v-if="job.status === 'running' || job.status === 'queued'"
              :indeterminate="job.status === 'queued'"
              :model-value="job.status === 'running' ? job.progress : undefined"
              size="18"
              width="2"
              color="primary"
              class="activity-item__icon"
            />
            <v-icon v-else-if="job.status === 'done'" size="18" color="success" class="activity-item__icon">
              mdi-file-music-outline
            </v-icon>
            <v-icon v-else size="18" color="error" class="activity-item__icon">mdi-alert-circle-outline</v-icon>
          </template>

          <v-list-item-title class="activity-item__title">{{ job.note_title }}</v-list-item-title>
          <v-list-item-subtitle v-if="job.status === 'failed'" class="activity-item__error">
            {{ job.error_message || 'Audioexport fehlgeschlagen' }}
          </v-list-item-subtitle>
          <v-list-item-subtitle v-else class="activity-item__types">
            Audioexport · {{ audioStatusLabel(job) }}
          </v-list-item-subtitle>

          <template #append>
            <div class="activity-item__actions">
              <v-btn
                v-if="job.status === 'done'"
                icon variant="text" size="x-small" color="success"
                :disabled="audioBusyIds.has(job.id)"
                title="Audiodatei herunterladen" aria-label="Audiodatei herunterladen"
                @click.stop="downloadAudio(job)"
              ><v-icon size="18">mdi-download</v-icon></v-btn>
              <v-btn
                v-if="job.status !== 'done'"
                icon variant="text" size="x-small"
                :disabled="audioBusyIds.has(job.id) || job.cancel_requested"
                title="Neu starten" aria-label="Audioexport neu starten"
                @click.stop="retryAudio(job)"
              ><v-icon size="17">mdi-refresh</v-icon></v-btn>
              <v-btn
                v-if="job.status === 'queued' || job.status === 'running'"
                icon variant="text" size="x-small"
                :disabled="audioBusyIds.has(job.id) || job.cancel_requested"
                title="Audioexport abbrechen" aria-label="Audioexport abbrechen"
                @click.stop="cancelAudio(job)"
              ><v-icon size="17">mdi-close</v-icon></v-btn>
              <v-btn
                v-else
                icon variant="text" size="x-small"
                :disabled="audioBusyIds.has(job.id)"
                title="Eintrag entfernen" aria-label="Audioexport entfernen"
                @click.stop="dismissAudio(job)"
              ><v-icon size="16">mdi-close</v-icon></v-btn>
            </div>
          </template>
        </v-list-item>

        <v-list-item v-for="group in visibleGroups" :key="group.documentId" class="activity-item">
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

          <template #append>
            <div class="activity-item__actions">
            <v-btn icon variant="text" size="x-small" :disabled="groupBusyIds.has(group.documentId)" title="Neu starten" aria-label="Dokumentverarbeitung neu starten" @click.stop="controlGroup(group, 'restart')"><v-icon size="17">mdi-refresh</v-icon></v-btn>
            <v-btn v-if="group.status !== 'failed'" icon variant="text" size="x-small" :disabled="groupBusyIds.has(group.documentId)" title="Beenden" aria-label="Dokumentverarbeitung beenden" @click.stop="controlGroup(group, 'cancel')"><v-icon size="17">mdi-stop</v-icon></v-btn>
            <v-btn
              icon
              variant="text"
              size="x-small"
              v-if="group.status === 'failed'"
              class="activity-item__dismiss"
              :disabled="isDismissing"
              title="Fehler entfernen"
              aria-label="Fehler entfernen"
              @click.stop="dismissGroup(group)"
            >
              <v-icon size="16">mdi-close</v-icon>
            </v-btn>
            </div>
          </template>
        </v-list-item>
      </v-list>

      <template v-if="failedGroups.length > 0 || failedAudioExports.length > 0">
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
            Fehler entfernen
          </v-btn>
        </div>
      </template>
    </v-card>
  </v-menu>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useTheme } from 'vuetify';
import { apiPost } from '../api/client.js';
import {
  cancelJob,
  restartJob,
  restartNoteAudioExport,
  cancelNoteAudioExport,
  confirmNoteAudioExportDownload,
  dismissFailedJobs,
  dismissJob,
  dismissNoteAudioExport,
  downloadNoteAudioExport,
  getJobActivity,
} from '../api/jobs.js';

const props = defineProps({
  presentation: {
    type: String,
    default: 'icon',
    validator: (value) => ['icon', 'menu-item'].includes(value),
  },
  buttonClass: {
    type: [String, Array, Object],
    default: '',
  },
});
const emit = defineEmits(['open-backup', 'status-change']);
const theme = useTheme();
const presentation = computed(() => props.presentation);
const buttonClass = computed(() => props.buttonClass);

const ACTIVE_POLL_MS = 4000;
const IDLE_POLL_MS = 15000;
const HIDDEN_POLL_MS = 60000;
const BURST_MS = 1500;   // schnelleres Polling-Intervall im Schub
const BURST_TICKS = 8;   // Anzahl der Schub-Durchläufe (~12 s)
const TYPE_LABELS = {
  OCR: 'Texterkennung',
  INDEX: 'Indexierung',
  EMBED: 'Embedding',
  TAG: 'Auto-Tagging'
};

const actionError = ref('');
const refreshing = ref(false);
const groupBusyIds = ref(new Set());
const activeFilter = ref('all');
const filters = [{ value: 'all', label: 'Alle' }, { value: 'active', label: 'Laufend' }, { value: 'failed', label: 'Beendet / Fehler' }];
const matchesFilter = (status) => activeFilter.value === 'all' || (activeFilter.value === 'active' ? ['queued', 'running'].includes(status) : status === 'failed');
const visibleGroups = computed(() => groups.value.filter(g => matchesFilter(g.status)));
const visibleAudioExports = computed(() => audioExports.value.filter(j => matchesFilter(j.status)));
const background = ref([]);
const backgroundBusy = ref(new Set());
const visibleBackground = computed(() => background.value.filter(j => activeFilter.value === 'all' || (activeFilter.value === 'active' ? ['queued', 'running', 'paused'].includes(j.status) : ['failed', 'cancelled'].includes(j.status))));
const jobs = ref([]);
const audioExports = ref([]);
const ocrBacklog = ref({ total: 0, done: 0, pending: 0, failed: 0 });
const backupFail = ref(null);
const menuOpen = ref(false);
const isDismissing = ref(false);
const audioBusyIds = ref(new Set());
let timer = null;
let burstTimer = null;
let refreshPromise = null;

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
const activeAudioExports = computed(() => audioExports.value.filter((job) => job.status === 'queued' || job.status === 'running'));
const readyAudioExports = computed(() => audioExports.value.filter((job) => job.status === 'done'));
const failedAudioExports = computed(() => audioExports.value.filter((job) => job.status === 'failed'));
// Gesamtfortschritt der Volltext-Erkennung (Dokument-Ebene), sichtbar auch in den
// Pausen zwischen den OCR-Häppchen.
const ocrPending = computed(() => Number(ocrBacklog.value?.pending || 0));
const ocrPercent = computed(() => {
  const total = Number(ocrBacklog.value?.total || 0);
  if (total <= 0) return 0;
  return Math.round((Number(ocrBacklog.value?.done || 0) / total) * 100);
});
const hasVisibleActivity = computed(() =>
  [...jobs.value, ...audioExports.value, ...background.value].some(job =>
    ['queued', 'running', 'paused'].includes(job.status)
  )
);
const hasBackupFail = computed(() => backupFail.value?.status === 'failed');
const isActive = computed(() => background.value.some(j => ['queued', 'running'].includes(j.status)) || activeGroups.value.length > 0 || activeAudioExports.value.length > 0 || ocrPending.value > 0);
// Fehlgeschlagene Dokument-Jobs plus ein evtl. fehlgeschlagenes Backup.
const failedCount = computed(() => background.value.filter(j => ['failed', 'cancelled'].includes(j.status)).length + failedGroups.value.length + failedAudioExports.value.length + (hasBackupFail.value ? 1 : 0));
const hasFailed = computed(() => failedCount.value > 0);
// Indikator anzeigen, wenn Jobs laufen, Dokumente auf Volltext warten ODER ein Backup fehlschlug.
const hasActivity = computed(() => background.value.length > 0 || groups.value.length > 0 || audioExports.value.length > 0 || ocrPending.value > 0 || hasBackupFail.value);
const badgeCount = computed(() =>
  isActive.value
    ? activeGroups.value.length + activeAudioExports.value.length + background.value.filter(j => ['queued', 'running'].includes(j.status)).length
    : (readyAudioExports.value.length || (hasFailed.value ? failedCount.value : 0))
);
const badgeColor = computed(() => (isActive.value ? 'primary' : (readyAudioExports.value.length ? 'success' : 'error')));

const ariaLabel = computed(() => {
  if (isActive.value) return `${activeGroups.value.length + activeAudioExports.value.length + background.value.filter(j => ['queued', 'running'].includes(j.status)).length} Vorgang/Vorgänge in Bearbeitung`;
  if (hasVisibleActivity.value) return 'Hintergrundaktivität pausiert';
  if (readyAudioExports.value.length) return `${readyAudioExports.value.length} Audiodatei(en) bereit`;
  if (hasFailed.value) return `${failedCount.value} fehlgeschlagen`;
  return 'Keine laufenden Prozesse';
});

const headerSub = computed(() => {
  const parts = [];
  const activeCount = activeGroups.value.length + activeAudioExports.value.length + background.value.filter(j => ['queued', 'running'].includes(j.status)).length;
  if (activeCount) parts.push(`${activeCount} in Bearbeitung`);
  if (readyAudioExports.value.length) parts.push(`${readyAudioExports.value.length} bereit`);
  if (failedCount.value) parts.push(`${failedCount.value} fehlgeschlagen`);
  return parts.join(' · ') || (ocrPending.value > 0 ? 'läuft im Hintergrund' : '');
});

watch(
  [hasActivity, badgeCount, badgeColor, ariaLabel],
  ([activity, count, color, label]) => {
    emit('status-change', {
      hasActivity: activity,
      badgeCount: count,
      badgeColor: color,
      ariaLabel: label,
    });
  },
  { immediate: true },
);

function openBackup() {
  menuOpen.value = false;
  emit('open-backup');
}

async function refresh() {
  if (refreshPromise) return refreshPromise;
  refreshing.value = true;
  refreshPromise = (async () => {
    try {
      const data = await getJobActivity();
      background.value = Array.isArray(data?.background) ? data.background : [];
      jobs.value = Array.isArray(data?.jobs) ? data.jobs : [];
      audioExports.value = Array.isArray(data?.audio_exports) ? data.audio_exports : [];
      void autoDownloadReadyAudioExports();
      ocrBacklog.value = data?.ocr_backlog ?? { total: 0, done: 0, pending: 0, failed: 0 };
      backupFail.value = data?.backup?.status === 'failed' ? data.backup : null;
    } catch {
      if (menuOpen.value) actionError.value = 'Aktivität konnte nicht geladen werden. Bitte erneut aktualisieren.';
    } finally {
      refreshing.value = false;
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

function schedulePoll(delay = null) {
  if (timer) window.clearTimeout(timer);
  const nextDelay = delay ?? (
    document.hidden ? HIDDEN_POLL_MS : (hasActivity.value ? ACTIVE_POLL_MS : IDLE_POLL_MS)
  );
  timer = window.setTimeout(async () => {
    await refresh();
    schedulePoll();
  }, nextDelay);
}

function handleVisibilityChange() {
  schedulePoll(document.hidden ? HIDDEN_POLL_MS : 0);
}

function audioStatusLabel(job) {
  if (job.cancel_requested) return 'wird abgebrochen';
  if (job.status === 'done') return 'bereit';
  if (job.status === 'queued') return 'wartet';
  const progress = `${Number(job.progress || 0)} %`;
  return job.phase ? `${job.phase} · ${progress}` : progress;
}

function setAudioBusy(jobId, busy) {
  const next = new Set(audioBusyIds.value);
  if (busy) next.add(jobId);
  else next.delete(jobId);
  audioBusyIds.value = next;
}

async function runAudioAction(job, action) {
  if (audioBusyIds.value.has(job.id)) return;
  setAudioBusy(job.id, true);
  try {
    actionError.value = '';
    await action();
    await refresh();
  } catch (error) {
    actionError.value = error.message || 'Aktion fehlgeschlagen. Bitte erneut versuchen.';
  } finally {
    setAudioBusy(job.id, false);
  }
}

function cancelAudio(job) {
  return runAudioAction(job, () => cancelNoteAudioExport(job.id));
}

function retryAudio(job) {
  return runAudioAction(job, () => restartNoteAudioExport(job.id));
}

function dismissAudio(job) {
  return runAudioAction(job, () => dismissNoteAudioExport(job.id));
}

function downloadAudio(job) {
  return runAudioAction(job, async () => {
    const blob = await downloadNoteAudioExport(job.id);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = job.filename || 'Notiz.wav';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    await confirmNoteAudioExportDownload(job.id);
  });
}

function autoDownloadReadyAudioExports() {
  for (const job of audioExports.value) {
    if (job.status !== 'done' || audioBusyIds.value.has(job.id)) continue;
    void downloadAudio(job);
  }
}

async function controlBackground(job, action) {
  if (backgroundBusy.value.has(job.id)) return;
  backgroundBusy.value = new Set([...backgroundBusy.value, job.id]);
  actionError.value = '';
  try { await apiPost(`/api/jobs/background/${job.kind}/${job.id}/${action}`); }
  catch (error) { actionError.value = error.message || 'Aktion fehlgeschlagen.'; }
  finally {
    await refresh();
    const next = new Set(backgroundBusy.value); next.delete(job.id); backgroundBusy.value = next;
  }
}

async function controlGroup(group, action) {
  if (groupBusyIds.value.has(group.documentId)) return;
  groupBusyIds.value = new Set([...groupBusyIds.value, group.documentId]);
  actionError.value = '';
  try {
    const restartedTypes = new Set();
    for (const job of jobs.value.filter(j => group.jobIds.includes(j.id) && (action !== 'cancel' || ['queued', 'running'].includes(j.status)))) {
      const type = job.type === 'EMBED' ? 'INDEX' : job.type;
      if (action === 'restart' && restartedTypes.has(type)) continue;
      await (action === 'cancel' ? cancelJob(job.id) : restartJob(job.id));
      restartedTypes.add(type);
    }
  } catch (error) {
    actionError.value = error.message || 'Aktion fehlgeschlagen. Bitte erneut versuchen.';
  } finally {
    await refresh();
    const next = new Set(groupBusyIds.value);
    next.delete(group.documentId);
    groupBusyIds.value = next;
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
  } catch (error) {
    actionError.value = error.message || 'Eintrag konnte nicht entfernt werden.';
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
    for (const job of failedAudioExports.value) {
      await dismissNoteAudioExport(job.id);
    }
    jobs.value = jobs.value.filter((j) => j.status !== 'failed');
    audioExports.value = audioExports.value.filter((job) => job.status !== 'failed');
    await refresh();
  } catch (error) {
    actionError.value = error.message || 'Fehler konnten nicht entfernt werden.';
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

onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('papermind:activity-refresh', poke);
  void refresh().finally(() => schedulePoll());
});

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  window.removeEventListener('papermind:activity-refresh', poke);
  if (timer) window.clearTimeout(timer);
  if (burstTimer) window.clearInterval(burstTimer);
});
</script>

<style scoped>
.activity-indicator-btn {
  --activity-badge-size: 13px;
  border-radius: 10px;
  color: var(--pm-muted) !important;
  transition:
    background-color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1)),
    color var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.activity-indicator-btn :deep(.v-icon) {
  color: inherit !important;
}

.activity-indicator-btn:hover,
.activity-indicator-btn:focus-visible {
  background: var(--pm-sidebar-hover) !important;
  color: var(--pm-accent) !important;
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

.activity-indicator-menu-item {
  min-height: 48px;
}

.activity-indicator-menu-item :deep(.v-list-item-subtitle) {
  font-size: 0.72rem;
}

.activity-indicator-menu-badge {
  margin-right: 4px;
}

.activity-card {
  color: rgb(var(--v-theme-on-surface)) !important;
  background: rgb(var(--v-theme-card)) !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 18px !important;
  width: min(440px, calc(100vw - 24px));
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.18) !important;
}
.activity-card :deep(.v-divider) {
  border-color: rgba(var(--v-theme-on-surface), 0.12);
  opacity: 1;
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
  color: rgb(var(--v-theme-on-surface)) !important;
  /* Die v-list bringt sonst ihren eigenen surface-Hintergrund mit und überdeckt
     den Karten-Hintergrund (account-menu-Look) → transparent durchscheinen lassen. */
  background: transparent !important;
}
.activity-list :deep(.v-list-item) {
  background: transparent;
}
.activity-item__title {
  color: rgb(var(--v-theme-on-surface));
}
.activity-item__types,
.activity-card__sub,
.activity-ocr__count {
  color: rgba(var(--v-theme-on-surface), 0.66);
  opacity: 1;
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
.activity-item__actions {
  display: flex;
  align-items: center;
  gap: 1px;
}
.activity-footer {
  padding: 4px 8px 8px;
}
.activity-footer .v-btn {
  text-transform: none;
  letter-spacing: normal;
}
.activity-item--clickable {
  cursor: pointer;
}
.activity-item--clickable:hover {
  background: color-mix(in srgb, rgb(var(--v-theme-error)) 9%, transparent);
}
</style>

<style scoped>
.activity-card__header-actions { display: flex; align-items: center; gap: 8px; }
.activity-filters { display: flex; gap: 4px; padding: 8px 12px; }
.activity-filters .v-btn { text-transform: none; letter-spacing: normal; border-radius: 10px; }
.activity-feedback { padding: 10px 14px; font-size: .8rem; color: rgb(var(--v-theme-error)); }
.activity-item { padding-block: 8px; }
</style>

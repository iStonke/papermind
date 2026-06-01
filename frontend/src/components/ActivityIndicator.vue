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
          offset-x="2"
          offset-y="2"
        >
          <v-icon v-if="isActive" size="20" color="primary">mdi-progress-clock</v-icon>
          <v-icon v-else size="20" color="error">mdi-alert-circle-outline</v-icon>
        </v-badge>
      </v-btn>
    </template>

    <v-card min-width="320" max-width="440" class="activity-card">
      <div class="activity-card__header">
        <span>Aktivität</span>
        <span class="activity-card__sub">{{ headerSub }}</span>
      </div>
      <v-divider />

      <div v-if="groups.length === 0" class="activity-empty">
        Keine laufenden Prozesse.
      </div>

      <v-list v-else density="compact" class="activity-list">
        <v-list-item v-for="group in groups" :key="group.documentId" class="activity-item">
          <template #prepend>
            <!-- Spinner nur für laufende Jobs OHNE Zahlenfortschritt; sonst statisches Icon -->
            <v-progress-circular
              v-if="group.status === 'running' && group.progress == null"
              indeterminate
              size="16"
              width="2"
              color="primary"
              class="activity-item__icon"
            />
            <v-icon v-else-if="group.status === 'failed'" size="16" class="activity-item__icon" color="error">
              mdi-alert-circle-outline
            </v-icon>
            <v-icon v-else size="16" class="activity-item__icon" color="medium-emphasis">
              mdi-progress-clock
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

          <!-- Ladebalken nur bei echtem 0–100-Fortschritt -->
          <v-progress-linear
            v-if="group.status === 'running' && group.progress != null"
            :model-value="group.progress"
            height="4"
            rounded
            color="primary"
            class="activity-item__progress"
          />
        </v-list-item>
      </v-list>
    </v-card>
  </v-menu>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getJobActivity } from '../api/jobs.js';

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
const menuOpen = ref(false);
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
    // Fortschritt: höchster Wert eines laufenden Jobs mit Zahl, sonst null (→ animierter Balken)
    const progresses = list
      .filter((j) => j.status === 'running' && j.progress != null)
      .map((j) => Number(j.progress));
    const progress = progresses.length ? Math.max(...progresses) : null;
    const types = [...new Set(list.map((j) => j.type))];
    const failedJob = list.find((j) => j.status === 'failed');
    result.push({
      documentId: entry.documentId,
      documentTitle: entry.documentTitle,
      status,
      progress,
      typesLabel: types.map(typeLabel).join(' · '),
      errorMessage: status === 'failed' ? (failedJob?.error_message || null) : null
    });
  }
  result.sort((a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status]);
  return result;
});

const activeGroups = computed(() => groups.value.filter((g) => g.status === 'running' || g.status === 'queued'));
const failedGroups = computed(() => groups.value.filter((g) => g.status === 'failed'));
const isActive = computed(() => activeGroups.value.length > 0);
const hasFailed = computed(() => failedGroups.value.length > 0);
// Indikator nur anzeigen, wenn es überhaupt etwas zu zeigen gibt.
const hasActivity = computed(() => groups.value.length > 0);
const badgeCount = computed(() =>
  isActive.value ? activeGroups.value.length : (hasFailed.value ? failedGroups.value.length : 0)
);
const badgeColor = computed(() => (isActive.value ? 'primary' : 'error'));

const ariaLabel = computed(() => {
  if (isActive.value) return `${activeGroups.value.length} Dokument(e) in Bearbeitung`;
  if (hasFailed.value) return `${failedGroups.value.length} fehlgeschlagen`;
  return 'Keine laufenden Prozesse';
});

const headerSub = computed(() => {
  const parts = [];
  if (activeGroups.value.length) parts.push(`${activeGroups.value.length} in Bearbeitung`);
  if (failedGroups.value.length) parts.push(`${failedGroups.value.length} fehlgeschlagen`);
  return parts.join(' · ') || 'im Leerlauf';
});

async function refresh() {
  try {
    const data = await getJobActivity();
    jobs.value = Array.isArray(data?.jobs) ? data.jobs : [];
  } catch {
    // Aktivität ist optional – Fehler beim Polling nicht stören lassen.
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
watch(
  () => groups.value.length,
  (count) => {
    if (menuOpen.value && count === 0) {
      menuOpen.value = false;
    }
  }
);

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
.activity-list {
  max-height: 340px;
  overflow-y: auto;
}
.activity-item__icon {
  margin-right: 8px;
}
.activity-item__doc {
  opacity: 0.7;
  font-weight: 400;
}
.activity-item__error {
  color: rgb(var(--v-theme-error));
  white-space: normal;
}
.activity-item__progress {
  margin-top: 6px;
}
</style>

<template>
  <div class="sys-panel">
    <!-- Hero / Kopf -->
    <SettingsInfoCard icon="mdi-raspberry-pi" :title="status?.host?.model || 'System'">
      <template #subtitle>
        <template v-if="status?.host?.hostname">{{ status.host.hostname }}</template>
        <template v-if="status?.host?.os"> · {{ status.host.os }}</template>
        <template v-if="uptimeLabel"> · seit {{ uptimeLabel }} online</template>
      </template>
      <template #actions>
        <v-btn
          icon
          variant="text"
          size="small"
          title="Aktualisieren"
          :loading="loading && !!status"
          @click="refresh"
        >
          <v-icon size="18">mdi-refresh</v-icon>
        </v-btn>
      </template>
    </SettingsInfoCard>

    <!-- Initialer Ladezustand -->
    <div v-if="!status && loading" class="sys-loading">
      <v-progress-circular indeterminate size="22" width="2" />
      <span>Systemstatus wird geladen…</span>
    </div>

    <!-- Fehlerzustand (kein Status verfügbar) -->
    <div v-else-if="!status && error" class="sys-error">
      <v-icon size="20" class="mr-2">mdi-alert-circle-outline</v-icon>
      <span>{{ error }}</span>
    </div>

    <template v-else-if="status">
      <!-- Gauges: CPU / RAM / Temperatur -->
      <div class="sys-gauges">
        <div class="sys-card sys-card--gauge">
          <div class="sys-card__head">
            <v-icon size="16">mdi-cpu-64-bit</v-icon>
            <span>CPU</span>
          </div>
          <SystemGauge
            :percent="status.cpu.usage_percent ?? 0"
            :display="status.cpu.usage_percent != null ? `${Math.round(status.cpu.usage_percent)} %` : '–'"
            :sublabel="cpuSub"
            :color="levelColor(status.cpu.usage_percent, 60, 85)"
          />
          <svg v-if="cpuHistory.length > 1" class="sys-spark" viewBox="0 0 100 28" preserveAspectRatio="none">
            <polyline :points="sparkPoints(cpuHistory, 100)" fill="none"
              :stroke="levelColor(status.cpu.usage_percent, 60, 85)" stroke-width="1.6" />
          </svg>
          <div v-else class="sys-spark sys-spark--empty" />
        </div>

        <div class="sys-card sys-card--gauge">
          <div class="sys-card__head">
            <v-icon size="16">mdi-memory</v-icon>
            <span>Arbeitsspeicher</span>
          </div>
          <SystemGauge
            :percent="status.memory.used_percent ?? 0"
            :display="status.memory.used_percent != null ? `${Math.round(status.memory.used_percent)} %` : '–'"
            :sublabel="memSub"
            :color="levelColor(status.memory.used_percent, 70, 90)"
          />
          <div class="sys-card__foot">{{ memFoot }}</div>
        </div>

        <div class="sys-card sys-card--gauge">
          <div class="sys-card__head">
            <v-icon size="16">mdi-thermometer</v-icon>
            <span>Temperatur</span>
          </div>
          <SystemGauge
            :percent="tempPercent"
            :display="status.temperature.celsius != null ? `${status.temperature.celsius.toFixed(1)} °C` : '–'"
            :sublabel="tempSub"
            :color="levelColor(status.temperature.celsius, 60, 75)"
          />
          <svg v-if="tempHistory.length > 1" class="sys-spark" viewBox="0 0 100 28" preserveAspectRatio="none">
            <polyline :points="sparkPoints(tempHistory, 90)" fill="none"
              :stroke="levelColor(status.temperature.celsius, 60, 75)" stroke-width="1.6" />
          </svg>
          <div v-else class="sys-spark sys-spark--empty" />
        </div>
      </div>

      <!-- Lüfter + Last -->
      <div class="sys-stats">
        <div class="sys-card sys-card--stat">
          <div class="sys-stat__icon" :class="{ 'sys-stat__icon--spin': fanActive }">
            <v-icon size="22">mdi-fan</v-icon>
          </div>
          <div class="sys-stat__body">
            <div class="sys-stat__label">Lüfter</div>
            <div class="sys-stat__value">{{ fanLabel }}</div>
          </div>
        </div>

        <div class="sys-card sys-card--stat">
          <div class="sys-stat__icon">
            <v-icon size="22">mdi-speedometer</v-icon>
          </div>
          <div class="sys-stat__body">
            <div class="sys-stat__label">Last (1 / 5 / 15 min)</div>
            <div class="sys-stat__value">{{ loadLabel }}</div>
          </div>
        </div>
      </div>

      <!-- Speicherplatz -->
      <div v-if="status.disks.length" class="sys-card sys-card--disks">
        <div class="sys-card__head">
          <v-icon size="16">mdi-harddisk</v-icon>
          <span>Speicherplatz</span>
        </div>
        <div v-for="disk in status.disks" :key="disk.path" class="sys-disk">
          <div class="sys-disk__top">
            <span class="sys-disk__label">{{ disk.label }}</span>
            <span class="sys-disk__detail">
              {{ formatBytes(disk.used_bytes) }} / {{ formatBytes(disk.total_bytes) }}
              <span class="sys-disk__free">· {{ formatBytes(disk.free_bytes) }} frei</span>
            </span>
          </div>
          <div class="sys-disk__bar">
            <div
              class="sys-disk__fill"
              :style="{ width: `${Math.min(100, disk.used_percent ?? 0)}%`, background: levelColor(disk.used_percent, 75, 90) }"
            />
          </div>
        </div>
      </div>

      <!-- Power-Aktionen -->
      <div class="sys-card sys-card--power">
        <div class="sys-card__head">
          <v-icon size="16">mdi-power</v-icon>
          <span>Energie</span>
        </div>
        <div v-if="status.power.pending" class="sys-power__pending">
          <v-progress-circular indeterminate size="16" width="2" class="mr-2" />
          {{ status.power.pending === 'poweroff' ? 'Herunterfahren' : 'Neustart' }} wurde eingereiht…
        </div>
        <div v-else class="sys-power__actions">
          <v-btn
            variant="tonal"
            color="primary"
            prepend-icon="mdi-restart"
            :disabled="!status.power.available || powerBusy"
            @click="askPower('reboot')"
          >
            Neustarten
          </v-btn>
          <v-btn
            variant="tonal"
            color="error"
            prepend-icon="mdi-power"
            :disabled="!status.power.available || powerBusy"
            @click="askPower('poweroff')"
          >
            Ausschalten
          </v-btn>
        </div>
        <div v-if="!status.power.available" class="sys-power__hint">
          Power-Aktionen sind nicht eingerichtet. Siehe <code>deploy/host-control</code>.
        </div>
      </div>
    </template>

    <!-- Bestätigung -->
    <v-dialog v-model="confirmOpen" max-width="440">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" :color="confirmAction === 'poweroff' ? 'error' : 'primary'">
            {{ confirmAction === 'poweroff' ? 'mdi-power' : 'mdi-restart' }}
          </v-icon>
          {{ confirmAction === 'poweroff' ? 'Raspberry Pi ausschalten?' : 'Raspberry Pi neu starten?' }}
        </v-card-title>
        <v-card-text>
          <template v-if="confirmAction === 'poweroff'">
            Der Pi wird heruntergefahren. PaperMind ist danach nicht mehr erreichbar,
            bis das Gerät wieder manuell eingeschaltet wird.
          </template>
          <template v-else>
            Der Pi startet neu. PaperMind ist für etwa eine Minute nicht erreichbar.
          </template>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmOpen = false">Abbrechen</v-btn>
          <v-btn
            :color="confirmAction === 'poweroff' ? 'error' : 'primary'"
            variant="flat"
            :loading="powerBusy"
            @click="confirmPower"
          >
            {{ confirmAction === 'poweroff' ? 'Ausschalten' : 'Neustarten' }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import SystemGauge from './SystemGauge.vue';
import { getSystemStatus, triggerPowerAction } from '../api/system';
import { notifyError, useNotifications } from '../stores/notifications';

const props = defineProps({
  active: { type: Boolean, default: false },
});

const { notify } = useNotifications();

const status = ref(null);
const loading = ref(false);
const error = ref('');
const cpuHistory = ref([]);
const tempHistory = ref([]);
const HISTORY_MAX = 40;
const POLL_MS = 4000;
let pollTimer = 0;

const confirmOpen = ref(false);
const confirmAction = ref(null);
const powerBusy = ref(false);

async function refresh() {
  if (loading.value) return;
  loading.value = true;
  try {
    const data = await getSystemStatus();
    status.value = data;
    error.value = '';
    if (data?.cpu?.usage_percent != null) pushHistory(cpuHistory, data.cpu.usage_percent);
    if (data?.temperature?.celsius != null) pushHistory(tempHistory, data.temperature.celsius);
  } catch (err) {
    error.value = err?.message || 'Systemstatus konnte nicht geladen werden.';
  } finally {
    loading.value = false;
  }
}

function pushHistory(arr, value) {
  arr.value.push(value);
  if (arr.value.length > HISTORY_MAX) arr.value.shift();
}

function startPolling() {
  stopPolling();
  refresh();
  pollTimer = window.setInterval(refresh, POLL_MS);
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = 0;
  }
}

watch(
  () => props.active,
  (active) => {
    if (active) startPolling();
    else stopPolling();
  },
  { immediate: true }
);

onBeforeUnmount(stopPolling);

// ── Power ──────────────────────────────────────────────────────────────────
function askPower(action) {
  confirmAction.value = action;
  confirmOpen.value = true;
}

async function confirmPower() {
  if (!confirmAction.value) return;
  powerBusy.value = true;
  try {
    const result = await triggerPowerAction(confirmAction.value);
    if (result?.accepted) {
      notify({ type: 'success', message: result.detail, critical: true });
      confirmOpen.value = false;
      await refresh();
    } else {
      notify({ type: 'error', message: result?.detail || 'Aktion nicht möglich.', critical: true });
    }
  } catch (err) {
    notifyError(err, 'Power-Aktion fehlgeschlagen.');
  } finally {
    powerBusy.value = false;
  }
}

// ── Formatierung & Farben ────────────────────────────────────────────────────
function levelColor(value, warn, danger) {
  if (value == null) return 'rgb(var(--v-theme-primary))';
  if (value >= danger) return 'rgb(var(--v-theme-error))';
  if (value >= warn) return '#f0a020';
  return '#3fae6a';
}

function formatBytes(bytes) {
  if (bytes == null) return '–';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  const digits = value >= 100 || i <= 1 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[i]}`;
}

function sparkPoints(history, max) {
  const data = history.value ?? history;
  const n = data.length;
  if (n < 2) return '';
  const top = Math.max(max, ...data) || 1;
  return data
    .map((v, idx) => {
      const x = (idx / (n - 1)) * 100;
      const y = 28 - (Math.max(0, Math.min(top, v)) / top) * 26 - 1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

const cpuSub = computed(() => {
  const cores = status.value?.cpu?.cores;
  return cores ? `${cores} Kerne` : '';
});

const memSub = computed(() => {
  const m = status.value?.memory;
  if (!m?.total_bytes) return '';
  return 'belegt';
});

const memFoot = computed(() => {
  const m = status.value?.memory;
  if (!m?.total_bytes) return '';
  return `${formatBytes(m.used_bytes)} / ${formatBytes(m.total_bytes)}`;
});

const tempPercent = computed(() => {
  const c = status.value?.temperature?.celsius;
  if (c == null) return 0;
  // 30 °C → 0 %, 90 °C → 100 %
  return Math.max(0, Math.min(100, ((c - 30) / 60) * 100));
});

const tempSub = computed(() => status.value?.temperature?.label || 'CPU');

const fanActive = computed(() => {
  const fan = status.value?.fan;
  if (!fan) return false;
  if (fan.rpm != null) return fan.rpm > 0;
  if (fan.level != null) return fan.level > 0;
  return !!fan.active;
});

const fanLabel = computed(() => {
  const fan = status.value?.fan;
  if (!fan || !fan.present) return 'nicht erkannt';
  if (fan.rpm != null) return fan.rpm > 0 ? `${fan.rpm} U/min` : 'aus';
  if (fan.level != null) {
    if (fan.max_level) return fan.level > 0 ? `Stufe ${fan.level}/${fan.max_level}` : 'aus';
    return fan.level > 0 ? `Stufe ${fan.level}` : 'aus';
  }
  return fan.active ? 'aktiv' : 'aus';
});

const loadLabel = computed(() => {
  const load = status.value?.cpu?.load_avg;
  if (!load?.length) return '–';
  return load.map((v) => v.toFixed(2)).join('  ·  ');
});

const uptimeLabel = computed(() => {
  const s = status.value?.host?.uptime_seconds;
  if (s == null) return '';
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const mins = Math.floor((s % 3600) / 60);
  if (days > 0) return `${days} ${days === 1 ? 'Tag' : 'Tagen'} ${hours} Std`;
  if (hours > 0) return `${hours} Std ${mins} min`;
  return `${mins} min`;
});
</script>

<style scoped>
.sys-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Hero kommt aus SettingsInfoCard; der sys-panel-Gap übernimmt den
   unteren Abstand, daher den Eigen-Abstand der Karte unten neutralisieren.
   Höhere Spezifität (.sys-panel ...), damit der Override zuverlässig greift. */
.sys-panel :deep(.settings-info-card) {
  margin-bottom: 0;
}

/* Lade-/Fehlerzustand */
.sys-loading,
.sys-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 4px;
  font-size: 0.9rem;
  opacity: 0.8;
}
.sys-error { color: rgb(var(--v-theme-error)); }

/* Karten */
.sys-card {
  border-radius: 16px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.02);
  padding: 14px;
}
.sys-card__head {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.78rem;
  font-weight: 600;
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 10px;
}

/* Gauge-Grid */
.sys-gauges {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.sys-card--gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.sys-card--gauge .sys-card__head { align-self: flex-start; }
.sys-card__foot {
  font-size: 0.78rem;
  opacity: 0.65;
  margin-top: 10px;
  font-variant-numeric: tabular-nums;
}
.sys-spark {
  width: 100%;
  height: 28px;
  margin-top: 10px;
  overflow: visible;
}
.sys-spark--empty { opacity: 0; }

/* Statistik-Karten (Lüfter / Last) */
.sys-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.sys-card--stat {
  display: flex;
  align-items: center;
  gap: 14px;
}
.sys-stat__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.6);
  flex-shrink: 0;
}
.sys-stat__icon--spin {
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}
.sys-stat__icon--spin :deep(.v-icon) {
  animation: sys-spin 1.8s linear infinite;
}
@keyframes sys-spin {
  to { transform: rotate(360deg); }
}
.sys-stat__body { min-width: 0; }
.sys-stat__label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  opacity: 0.55;
}
.sys-stat__value {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

/* Speicherplatz */
.sys-disk { margin-bottom: 14px; }
.sys-disk:last-child { margin-bottom: 0; }
.sys-disk__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.sys-disk__label { font-size: 0.85rem; font-weight: 600; }
.sys-disk__detail {
  font-size: 0.78rem;
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.sys-disk__free { opacity: 0.7; }
.sys-disk__bar {
  height: 9px;
  border-radius: 6px;
  background: rgba(var(--v-theme-on-surface), 0.1);
  overflow: hidden;
}
.sys-disk__fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.6s ease, background 0.4s ease;
}

/* Power */
.sys-power__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.sys-power__pending {
  display: flex;
  align-items: center;
  font-size: 0.88rem;
  color: rgb(var(--v-theme-primary));
}
.sys-power__hint {
  font-size: 0.76rem;
  opacity: 0.6;
  margin-top: 10px;
}
.sys-power__hint code {
  font-size: 0.72rem;
  padding: 1px 5px;
  border-radius: 5px;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

@media (max-width: 620px) {
  .sys-gauges { grid-template-columns: 1fr; }
  .sys-stats { grid-template-columns: 1fr; }
}
</style>

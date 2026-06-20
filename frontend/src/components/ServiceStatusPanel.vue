<template>
  <div class="services-panel">
    <SettingsInfoCard icon="mdi-server-network" title="Dienste">
      <template #subtitle>
        {{ summaryLabel }}
        <template v-if="lastUpdatedLabel"> · aktualisiert {{ lastUpdatedLabel }}</template>
      </template>
      <template #actions>
        <v-btn
          icon
          variant="text"
          size="small"
          title="Dienstestatus aktualisieren"
          :loading="loading"
          @click="refresh"
        >
          <v-icon size="18">mdi-refresh</v-icon>
        </v-btn>
      </template>
    </SettingsInfoCard>

    <div v-if="!services.length && loading" class="services-loading">
      <v-progress-circular indeterminate size="22" width="2" />
      <span>Dienstestatus wird geladen...</span>
    </div>

    <div v-else-if="!services.length && error" class="services-error">
      <v-icon size="20">mdi-alert-circle-outline</v-icon>
      <span>{{ error }}</span>
    </div>

    <div v-else class="services-list">
      <div
        v-for="service in services"
        :key="service.key"
        class="service-row"
        :class="`service-row--${service.status || 'unknown'}`"
      >
        <div class="service-row__lamp" :title="statusLabel(service.status)" />

        <div class="service-row__main">
          <div class="service-row__top">
            <div class="service-row__title">{{ service.label }}</div>
            <div class="service-row__status">{{ statusLabel(service.status) }}</div>
          </div>
          <div class="service-row__description">{{ service.description }}</div>
          <div class="service-row__detail">
            <span>{{ service.detail || 'Keine Details verfügbar' }}</span>
            <span v-if="service.latency_ms != null"> · {{ service.latency_ms }} ms</span>
            <span v-if="service.endpoint"> · {{ service.endpoint }}</span>
          </div>
        </div>

        <div class="service-row__controls">
          <v-menu
            v-if="Array.isArray(service.actions) && service.actions.length"
            location="bottom end"
            transition="fade-transition"
          >
            <template #activator="{ props: menuProps }">
              <v-btn
                v-bind="menuProps"
                class="service-row__menu-btn"
                icon
                variant="text"
                size="small"
                :aria-label="`${service.label} Aktionen`"
              >
                <v-icon size="19">mdi-dots-vertical</v-icon>
              </v-btn>
            </template>

            <v-list class="service-actions-menu" density="compact" min-width="220">
              <v-list-item
                v-for="action in service.actions"
                :key="`${service.key}-${action.action}`"
                :disabled="!action.enabled || !!actionBusy[`${service.key}:${action.action}`]"
                @click="runAction(service, action)"
              >
                <template #prepend>
                  <v-progress-circular
                    v-if="!!actionBusy[`${service.key}:${action.action}`]"
                    indeterminate
                    size="16"
                    width="2"
                  />
                  <v-icon v-else size="17" :color="action.destructive ? 'error' : undefined">
                    {{ actionIcon(action.action) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ action.label }}</v-list-item-title>
                <v-list-item-subtitle v-if="action.reason">{{ action.reason }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-menu>

          <v-switch
            v-if="service.configurable"
            class="service-row__switch"
            color="primary"
            density="compact"
            hide-details
            inset
            :model-value="service.enabled"
            :loading="!!saving[service.key]"
            :disabled="!!saving[service.key]"
            :aria-label="`${service.label} in PaperMind verwenden`"
            @update:model-value="(value) => updateServiceEnabled(service, value)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import { getBaseUrl } from '../api/client';
import { getServiceStatus, runServiceAction } from '../api/system';
import { notifyError, useNotifications } from '../stores/notifications';
import { useSettingsStore } from '../stores/settings';

const props = defineProps({
  active: { type: Boolean, default: false },
});

const settingsStore = useSettingsStore();
const { notify } = useNotifications();

const services = ref([]);
const overallStatus = ref('unknown');
const collectedAt = ref('');
const loading = ref(false);
const error = ref('');
const saving = ref({});
const actionBusy = ref({});
const POLL_MS = 15000;
let pollTimer = 0;

const summaryLabel = computed(() => {
  switch (overallStatus.value) {
    case 'ok':
      return 'Alle aktiven Dienste laufen';
    case 'warning':
      return 'Mindestens ein Dienst braucht Aufmerksamkeit';
    case 'error':
      return 'Mindestens ein aktiver Dienst ist nicht erreichbar';
    default:
      return 'Status der PaperMind-Dienste';
  }
});

const lastUpdatedLabel = computed(() => {
  if (!collectedAt.value) return '';
  const date = new Date(collectedAt.value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
});

async function refresh() {
  if (loading.value) return;
  loading.value = true;
  try {
    const data = await getServiceStatus();
    services.value = Array.isArray(data?.services) ? data.services : [];
    overallStatus.value = data?.status || 'unknown';
    collectedAt.value = data?.collected_at || '';
    error.value = '';
  } catch (err) {
    error.value = err?.message || 'Dienstestatus konnte nicht geladen werden.';
  } finally {
    loading.value = false;
  }
}

function replaceService(updatedService) {
  if (!updatedService?.key) return;
  services.value = services.value.map((service) => (
    service.key === updatedService.key ? updatedService : service
  ));
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

function statusLabel(status) {
  switch (status) {
    case 'ok':
      return 'Aktiv';
    case 'warning':
      return 'Warnung';
    case 'error':
      return 'Fehler';
    case 'disabled':
      return 'Deaktiviert';
    default:
      return 'Unbekannt';
  }
}

function actionIcon(action) {
  switch (action) {
    case 'check':
      return 'mdi-refresh';
    case 'start':
      return 'mdi-play';
    case 'stop':
      return 'mdi-stop';
    case 'restart':
      return 'mdi-restart';
    default:
      return 'mdi-dots-horizontal';
  }
}

function patchForService(service, enabled) {
  switch (service?.setting_key) {
    case 'ollama.enabled':
      return { ollama: { enabled: Boolean(enabled) } };
    case 'documents.auto_ocr':
      return { documents: { auto_ocr: Boolean(enabled) } };
    default:
      return null;
  }
}

async function updateServiceEnabled(service, enabled) {
  const patch = patchForService(service, enabled);
  if (!patch) return;

  saving.value = { ...saving.value, [service.key]: true };
  try {
    await settingsStore.patchSettings(getBaseUrl(), patch);
    notify({
      type: 'success',
      message: `${service.label} wurde ${enabled ? 'aktiviert' : 'deaktiviert'}.`,
    });
    await refresh();
  } catch (err) {
    notifyError(err, `${service.label} konnte nicht geändert werden.`);
  } finally {
    const next = { ...saving.value };
    delete next[service.key];
    saving.value = next;
  }
}

async function runAction(service, action) {
  if (!service?.key || !action?.action || !action.enabled) return;
  const busyKey = `${service.key}:${action.action}`;
  actionBusy.value = { ...actionBusy.value, [busyKey]: true };
  try {
    const result = await runServiceAction(service.key, action.action);
    if (result?.service) replaceService(result.service);
    notify({
      type: result?.accepted ? 'success' : 'warning',
      title: service.label,
      message: result?.detail || 'Aktion abgeschlossen.',
    });
  } catch (err) {
    notifyError(err, `${service.label}: Aktion fehlgeschlagen.`);
  } finally {
    const next = { ...actionBusy.value };
    delete next[busyKey];
    actionBusy.value = next;
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
</script>

<style scoped>
.services-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.services-panel :deep(.settings-info-card) {
  margin-bottom: 0;
}

.services-loading,
.services-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 22px 4px;
  font-size: 0.9rem;
  opacity: 0.82;
}

.services-error {
  color: rgb(var(--v-theme-error));
}

.services-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.service-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 74px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 14px;
  background: rgba(var(--v-theme-on-surface), 0.025);
}

.service-row__lamp {
  width: 11px;
  height: 11px;
  border-radius: 999px;
  flex: 0 0 auto;
  background: rgba(var(--v-theme-on-surface), 0.34);
  box-shadow: 0 0 0 4px rgba(var(--v-theme-on-surface), 0.06);
}

.service-row--ok .service-row__lamp {
  background: #3fae6a;
  box-shadow: 0 0 0 4px rgba(63, 174, 106, 0.14);
}

.service-row--warning .service-row__lamp {
  background: #f0a020;
  box-shadow: 0 0 0 4px rgba(240, 160, 32, 0.16);
}

.service-row--error .service-row__lamp {
  background: rgb(var(--v-theme-error));
  box-shadow: 0 0 0 4px rgba(var(--v-theme-error), 0.14);
}

.service-row--disabled .service-row__lamp {
  background: rgba(var(--v-theme-on-surface), 0.34);
  box-shadow: 0 0 0 4px rgba(var(--v-theme-on-surface), 0.07);
}

.service-row__main {
  min-width: 0;
  flex: 1;
}

.service-row__top {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.service-row__title {
  font-size: 0.96rem;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}

.service-row__status {
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.62;
}

.service-row__description {
  margin-top: 2px;
  font-size: 0.82rem;
  opacity: 0.72;
}

.service-row__detail {
  margin-top: 4px;
  font-size: 0.76rem;
  line-height: 1.35;
  opacity: 0.58;
  word-break: break-word;
}

.service-row__controls {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.service-row__menu-btn {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.service-row__switch {
  flex: 0 0 auto;
}

.service-actions-menu :deep(.v-list-item-title) {
  font-size: 0.86rem;
}

.service-actions-menu :deep(.v-list-item-subtitle) {
  max-width: 260px;
  white-space: normal;
  line-height: 1.25;
}

@media (max-width: 700px) {
  .service-row {
    align-items: flex-start;
  }

  .service-row__controls {
    align-items: flex-end;
    margin-top: -4px;
  }
}
</style>

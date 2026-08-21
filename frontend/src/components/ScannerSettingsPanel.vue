<template>
  <div class="scanner-settings-panel">
    <SettingsInfoCard
      icon="mdi-scanner"
      title="Scanner"
      subtitle="Verfügbare Geräte finden, hinzufügen und verwalten."
    >
      <template #actions>
        <v-btn
          icon="mdi-refresh"
          variant="text"
          size="small"
          :loading="loading"
          aria-label="Scanner aktualisieren"
          title="Scanner aktualisieren"
          @click="loadScanners"
        />
      </template>
    </SettingsInfoCard>

    <div v-if="loading && scanners.length === 0" class="scanner-state" role="status">
      <v-progress-circular indeterminate size="20" width="2" />
      <span>Scanner werden gesucht…</span>
    </div>

    <div v-else-if="errorMessage && scanners.length === 0" class="scanner-state scanner-state--error">
      <v-icon size="20">mdi-alert-circle-outline</v-icon>
      <span>{{ errorMessage }}</span>
      <v-btn variant="text" size="small" @click="loadScanners">Erneut versuchen</v-btn>
    </div>

    <template v-else>
      <div class="scanner-overview">
        <div v-if="!hasVisibleScanners" class="scanner-empty">
          <v-icon size="28">mdi-scanner-off</v-icon>
          <div>
            <div class="scanner-empty__title">Keine Scanner gefunden</div>
            <div class="scanner-empty__text">
              Schließe einen Scanner an. Die Geräteliste aktualisiert sich automatisch.
            </div>
          </div>
        </div>

        <template v-else>
          <section
            v-for="section in scannerSections"
            :key="section.key"
            class="scanner-section"
          >
            <div class="scanner-section__title">{{ section.title }}</div>
            <div class="scanner-device-list" role="listbox" :aria-label="section.title">
              <template v-for="scanner in section.scanners" :key="scanner.id">
                <!-- Hinzugefügt: auswählbare Zeile, öffnet die Konfiguration -->
                <button
                  v-if="section.key === 'added'"
                  type="button"
                  class="scanner-device-row"
                  :class="{ 'is-selected': selectedScannerId === scanner.id }"
                  role="option"
                  :aria-selected="selectedScannerId === scanner.id"
                  @click="selectScanner(scanner)"
                >
                  <span class="scanner-device-row__icon">
                    <v-icon size="24">mdi-printer-eye</v-icon>
                  </span>
                  <span class="scanner-device-row__body">
                    <span class="scanner-device-row__name">{{ scannerDisplayName(scanner) }}</span>
                    <span class="scanner-device-row__meta">{{ scannerSecondaryLabel(scanner) }}</span>
                  </span>
                  <v-icon
                    class="scanner-device-row__selection"
                    :class="{ 'is-visible': selectedScannerId === scanner.id }"
                    size="18"
                    aria-hidden="true"
                  >
                    mdi-check
                  </v-icon>
                </button>

                <!-- Verfügbar: statische Zeile, einzige Aktion = Inline-Hinzufügen -->
                <div v-else class="scanner-device-row scanner-device-row--static" role="option">
                  <span class="scanner-device-row__icon">
                    <v-icon size="24">mdi-printer-eye</v-icon>
                  </span>
                  <span class="scanner-device-row__body">
                    <span class="scanner-device-row__name">{{ scannerDisplayName(scanner) }}</span>
                    <span class="scanner-device-row__meta">{{ scannerSecondaryLabel(scanner) }}</span>
                  </span>
                  <v-btn
                    class="scanner-device-row__add"
                    icon="mdi-plus"
                    variant="tonal"
                    color="primary"
                    size="small"
                    :loading="addingIds.has(scanner.id)"
                    :disabled="addingIds.size > 0"
                    :aria-label="`${scannerDisplayName(scanner)} hinzufügen`"
                    :title="`${scannerDisplayName(scanner)} hinzufügen`"
                    @click="addScanner(scanner)"
                  />
                </div>
              </template>
            </div>
          </section>
        </template>

        <div v-if="selectedScanner" class="scanner-selection">
          <div v-if="selectedScanner.configured" class="scanner-config">
            <div class="scanner-config__heading">
              <span>Konfiguration</span>
            </div>

            <div class="scanner-detail__form">
              <v-text-field
                v-model="selectedScanner.name"
                label="Name"
                density="compact"
                variant="outlined"
                hide-details
                :disabled="savingIds.has(selectedScanner.id)"
                @update:model-value="onScannerDraftChanged"
              />

              <div class="scanner-detail__toggle-row">
                <div>
                  <div class="scanner-detail__label">Scanner verwenden</div>
                  <div class="scanner-detail__hint">{{ scannerInboxHint(selectedScanner) }}</div>
                </div>
                <v-switch
                  v-model="selectedScanner.enabled"
                  color="primary"
                  density="compact"
                  hide-details
                  inset
                  aria-label="Scanner verwenden"
                  @update:model-value="onScannerDraftChanged(200)"
                />
              </div>

              <div class="scanner-detail__toggle-row">
                <div>
                  <div class="scanner-detail__label">Seiten sofort senden</div>
                  <div class="scanner-detail__hint">
                    Jede Seite erscheint direkt im Importfenster, ohne einen Stapel abzuschließen.
                  </div>
                </div>
                <v-switch
                  v-model="selectedScanner.live_page_mode"
                  color="primary"
                  density="compact"
                  hide-details
                  inset
                  :disabled="savingIds.has(selectedScanner.id)"
                  aria-label="Seiten sofort senden"
                  @update:model-value="onScannerDraftChanged(200)"
                />
              </div>

              <div class="scanner-detail__technical">
                <div class="scanner-detail__technical-label">Gerät</div>
                <div class="scanner-detail__technical-value">
                  {{ selectedScanner.hardware_name || selectedScanner.device_key }}
                </div>
                <div class="scanner-detail__technical-meta">{{ scannerLastSeenLabel(selectedScanner) }}</div>
              </div>

              <div class="scanner-detail__access">
                <div class="scanner-detail__toggle-row">
                  <div>
                    <div class="scanner-detail__label">Zugriff einschränken</div>
                    <div class="scanner-detail__hint">
                      Nur ausgewählte Benutzer sehen neue Scans und dürfen diesen Scanner auslösen.
                    </div>
                  </div>
                  <v-switch
                    :model-value="selectedScanner.access_restricted"
                    color="primary"
                    density="compact"
                    hide-details
                    inset
                    :disabled="savingIds.has(selectedScanner.id)"
                    aria-label="Zugriff einschränken"
                    @update:model-value="setAccessRestricted"
                  />
                </div>

                <v-autocomplete
                  v-if="selectedScanner.access_restricted"
                  v-model="selectedScanner.recipient_user_ids"
                  :items="userOptions"
                  label="Berechtigte Benutzer"
                  density="compact"
                  variant="outlined"
                  hide-details
                  chips
                  closable-chips
                  multiple
                  :disabled="savingIds.has(selectedScanner.id)"
                  :menu-props="{ attach: 'body', zIndex: 6000 }"
                  @update:model-value="onScannerDraftChanged(200)"
                >
                  <template #chip="{ props: chipProps, item }">
                    <v-chip v-bind="chipProps" size="small" class="scanner-recipient-chip">
                      <template #prepend>
                        <UserAvatar :user="item.raw.user" :size="20" />
                      </template>
                      {{ item.title }}
                    </v-chip>
                  </template>
                  <template #item="{ props: itemProps, item }">
                    <v-list-item v-bind="itemProps">
                      <template #prepend><UserAvatar :user="item.raw.user" :size="28" /></template>
                    </v-list-item>
                  </template>
                </v-autocomplete>

                <div
                  v-if="selectedScanner.access_restricted && selectedScanner.recipient_user_ids.length === 0"
                  class="scanner-detail__access-warning"
                >
                  Wähle mindestens einen berechtigten Benutzer aus.
                </div>
              </div>

              <div class="scanner-detail__danger">
                <div>
                  <div class="scanner-detail__label">Scanner entfernen</div>
                  <div class="scanner-detail__hint">
                    Konfiguration löschen; das Gerät bleibt verfügbar und kann erneut hinzugefügt werden.
                  </div>
                </div>
                <v-btn
                  variant="text"
                  color="error"
                  size="small"
                  prepend-icon="mdi-delete-outline"
                  :disabled="savingIds.has(selectedScanner.id) || removingId === selectedScanner.id"
                  @click="requestRemoveScanner(selectedScanner)"
                >
                  Entfernen
                </v-btn>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <DestructiveDialog
      v-model="removeConfirmOpen"
      max-width="460"
      title="Scanner entfernen?"
      :header-subtitle="removeTarget ? scannerDisplayName(removeTarget) : ''"
      primary-text="Entfernen"
      secondary-text="Abbrechen"
      icon="mdi-scanner-off"
      :loading="Boolean(removingId)"
      :persistent="Boolean(removingId)"
      @primary="confirmRemoveScanner"
    >
      <p class="scanner-remove-dialog__copy">
        Der Scanner wird deaktiviert und aus PaperMind entfernt. Ist er weiterhin angeschlossen,
        kann er später erneut hinzugefügt werden. Bereits importierte Dokumente bleiben erhalten.
      </p>
    </DestructiveDialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  configureScanner,
  listScanners,
  removeScannerConfiguration,
  updateScanner
} from '../api/scanners.js';
import { listUsers } from '../api/users.js';
import { useAuthStore } from '../stores/auth.js';
import { notifyError } from '../stores/notifications.js';
import DestructiveDialog from './DestructiveDialog.vue';
import SettingsInfoCard from './SettingsInfoCard.vue';
import UserAvatar from './UserAvatar.vue';

const auth = useAuthStore();

const scanners = ref([]);
const users = ref([]);
const loading = ref(false);
const errorMessage = ref('');
const selectedScannerId = ref('');
const addingIds = ref(new Set());
const removeConfirmOpen = ref(false);
const removeTargetId = ref('');
const removingId = ref('');
const savingIds = ref(new Set());
const saveTimers = new Map();
const pendingSaveIds = new Set();
let discoveryRefreshTimer = null;

const selectedScanner = computed(() => (
  scanners.value.find((scanner) => scanner.id === selectedScannerId.value) || null
));
const removeTarget = computed(() => (
  scanners.value.find((scanner) => scanner.id === removeTargetId.value) || null
));
const addedScanners = computed(() => scanners.value.filter((scanner) => scanner.configured));
const availableScanners = computed(() => scanners.value.filter(
  (scanner) => !scanner.configured && scanner.available
));
const hasVisibleScanners = computed(() => (
  addedScanners.value.length > 0 || availableScanners.value.length > 0
));
const scannerSections = computed(() => [
  { key: 'added', title: 'Hinzugefügt', scanners: addedScanners.value },
  { key: 'available', title: 'Verfügbar', scanners: availableScanners.value }
].filter((section) => section.scanners.length > 0));
const userOptions = computed(() => users.value
  .filter((user) => user?.is_active !== false)
  .map((user) => ({
    title: user.display_name || user.username,
    value: user.id,
    user,
    props: { subtitle: user.email || user.username }
  })));
function normalizeScanner(scanner) {
  const recipientUserIds = Array.isArray(scanner?.recipients)
    ? scanner.recipients.map((user) => String(user?.id || '').trim()).filter(Boolean)
    : [];
  return {
    id: String(scanner?.id || '').trim(),
    device_key: String(scanner?.device_key || '').trim(),
    connection_uri: String(scanner?.connection_uri || '').trim(),
    hardware_name: String(scanner?.hardware_name || '').trim(),
    name: String(scanner?.name || scanner?.hardware_name || scanner?.device_key || '').trim(),
    configured: scanner?.configured !== false,
    available: Boolean(scanner?.available),
    enabled: scanner?.enabled !== false,
    live_page_mode: scanner?.live_page_mode === true,
    last_seen_at: scanner?.last_seen_at || null,
    discovered_at: scanner?.discovered_at || null,
    access_restricted: recipientUserIds.length > 0,
    recipient_user_ids: recipientUserIds
  };
}

function scannerDisplayName(scanner) {
  return scanner?.name || scanner?.hardware_name || 'Scanner';
}

function scannerSecondaryLabel(scanner) {
  if (!scanner?.configured) {
    return scanner.hardware_name && scanner.hardware_name !== scanner.name
      ? scanner.hardware_name
      : 'Bereit zum Hinzufügen';
  }
  const deviceLabel = scanner.hardware_name && scanner.hardware_name !== scanner.name
    ? scanner.hardware_name
    : '';
  const connectionLabel = !scanner.enabled
    ? 'Deaktiviert'
    : scanner.available ? 'Bereit' : 'Nicht verbunden';
  return [deviceLabel, connectionLabel].filter(Boolean).join(' · ');
}

function scannerLastSeenLabel(scanner) {
  const value = scanner?.discovered_at || scanner?.last_seen_at;
  if (!value) return 'Noch nicht verbunden';
  try {
    return `Zuletzt erkannt ${new Intl.DateTimeFormat('de-DE', {
      dateStyle: 'short',
      timeStyle: 'short'
    }).format(new Date(value))}`;
  } catch {
    return 'Zuletzt erkannt';
  }
}

function scannerInboxHint(scanner) {
  return scanner?.access_restricted
    ? 'Neue Scans sind nur für die ausgewählten Benutzer sichtbar.'
    : 'Neue Scans erscheinen im gemeinsamen Scan-Eingang.';
}

function selectScanner(scanner) {
  if (!scanner?.id) return;
  selectedScannerId.value = scanner.id;
}

function setAccessRestricted(nextValue) {
  const scanner = selectedScanner.value;
  if (!scanner) return;
  scanner.access_restricted = Boolean(nextValue);
  if (!scanner.access_restricted) {
    scanner.recipient_user_ids = [];
  } else if (scanner.recipient_user_ids.length === 0) {
    const currentUserId = String(auth.user?.id || '').trim();
    const defaultUser = users.value.find((user) => String(user?.id || '') === currentUserId)
      || users.value[0];
    const defaultUserId = String(defaultUser?.id || '').trim();
    if (defaultUserId) scanner.recipient_user_ids = [defaultUserId];
  }
  onScannerDraftChanged(200);
}

async function addScanner(scanner) {
  if (!scanner?.id || scanner.configured || addingIds.value.has(scanner.id)) return;
  const nextAdding = new Set(addingIds.value);
  nextAdding.add(scanner.id);
  addingIds.value = nextAdding;
  try {
    const saved = await configureScanner(scanner.id, {
      name: String(scanner.name || scanner.hardware_name || 'Scanner').trim(),
      enabled: true,
      recipient_user_ids: []
    });
    const index = scanners.value.findIndex((item) => item.id === scanner.id);
    if (index >= 0) scanners.value[index] = normalizeScanner(saved);
    // Frisch hinzugefügtes Gerät auswählen, damit die Konfiguration direkt aufgeht.
    selectedScannerId.value = scanner.id;
  } catch (error) {
    notifyError(error, 'Scanner konnte nicht hinzugefügt werden.');
  } finally {
    const remaining = new Set(addingIds.value);
    remaining.delete(scanner.id);
    addingIds.value = remaining;
  }
}

function requestRemoveScanner(scanner) {
  if (!scanner?.id || !scanner.configured || savingIds.value.has(scanner.id) || removingId.value) return;
  if (saveTimers.has(scanner.id)) {
    clearTimeout(saveTimers.get(scanner.id));
    saveTimers.delete(scanner.id);
  }
  pendingSaveIds.delete(scanner.id);
  removeTargetId.value = scanner.id;
  removeConfirmOpen.value = true;
}

async function confirmRemoveScanner() {
  const scanner = removeTarget.value;
  if (!scanner?.id || removingId.value) return;
  removingId.value = scanner.id;
  try {
    const saved = await removeScannerConfiguration(scanner.id);
    const index = scanners.value.findIndex((item) => item.id === scanner.id);
    if (index >= 0) scanners.value[index] = normalizeScanner(saved);
    removeConfirmOpen.value = false;
    removeTargetId.value = '';
    // Entferntes Gerät wandert in „Verfügbar" (nicht mehr auswählbar) -> Auswahl leeren.
    if (selectedScannerId.value === scanner.id) selectedScannerId.value = '';
  } catch (error) {
    notifyError(error, 'Scanner konnte nicht entfernt werden.');
  } finally {
    removingId.value = '';
  }
}

async function loadScanners() {
  if (loading.value) return;
  loading.value = true;
  errorMessage.value = '';
  try {
    const [scannerPayload, userPayload] = await Promise.all([listScanners(), listUsers()]);
    scanners.value = (Array.isArray(scannerPayload?.items) ? scannerPayload.items : [])
      .map(normalizeScanner)
      .filter((scanner) => scanner.id);
    users.value = Array.isArray(userPayload?.items) ? userPayload.items : [];
    const stillVisible = scanners.value.some((scanner) => (
      scanner.id === selectedScannerId.value && (scanner.configured || scanner.available)
    ));
    if (selectedScannerId.value && !stillVisible) {
      selectedScannerId.value = '';
    }
  } catch (error) {
    errorMessage.value = error?.message || 'Scanner konnten nicht geladen werden.';
    notifyError(error, 'Scanner konnten nicht geladen werden.');
  } finally {
    loading.value = false;
  }
}

function onScannerDraftChanged(delay = 650) {
  const scanner = selectedScanner.value;
  if (!scanner?.configured) return;
  if (saveTimers.has(scanner.id)) clearTimeout(saveTimers.get(scanner.id));
  saveTimers.set(scanner.id, setTimeout(() => {
    saveTimers.delete(scanner.id);
    void saveScanner(scanner);
  }, Number(delay) || 0));
}

async function saveScanner(scanner) {
  if (!scanner?.id || !String(scanner.name || '').trim()) return;
  if (scanner.access_restricted && scanner.recipient_user_ids.length === 0) return;
  if (savingIds.value.has(scanner.id)) {
    pendingSaveIds.add(scanner.id);
    return;
  }
  const next = new Set(savingIds.value);
  next.add(scanner.id);
  savingIds.value = next;
  try {
    await updateScanner(scanner.id, {
      name: String(scanner.name).trim(),
      enabled: Boolean(scanner.enabled),
      live_page_mode: Boolean(scanner.live_page_mode),
      recipient_user_ids: scanner.access_restricted ? scanner.recipient_user_ids : []
    });
  } catch (error) {
    notifyError(error, 'Scanner-Einstellungen konnten nicht gespeichert werden.');
  } finally {
    const remaining = new Set(savingIds.value);
    remaining.delete(scanner.id);
    savingIds.value = remaining;
    if (pendingSaveIds.delete(scanner.id)) void saveScanner(scanner);
  }
}

onMounted(() => {
  void loadScanners();
  discoveryRefreshTimer = setInterval(() => {
    if (!selectedScannerId.value) void loadScanners();
  }, 12_000);
});
onBeforeUnmount(() => {
  if (discoveryRefreshTimer) clearInterval(discoveryRefreshTimer);
  saveTimers.forEach((timer) => clearTimeout(timer));
});
</script>

<style scoped>
.scanner-settings-panel { width: 100%; }
.scanner-state,
.scanner-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 88px;
  padding: 16px 12px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.86rem;
}
.scanner-state--error { color: rgb(var(--v-theme-error)); }
.scanner-overview { display: grid; gap: 18px; }
.scanner-section { display: grid; gap: 8px; }
.scanner-section__title {
  color: rgba(var(--v-theme-on-surface), 0.48);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.scanner-empty {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.09);
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.025);
}
.scanner-empty__title { color: rgba(var(--v-theme-on-surface), 0.84); font-weight: 650; }
.scanner-empty__text { margin-top: 2px; font-size: 0.8rem; }
.scanner-device-list {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.09);
  border-radius: 12px;
  background: rgba(var(--v-theme-surface), 0.56);
}
.scanner-device-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 66px;
  padding: 10px 12px;
  color: inherit;
  text-align: left;
  border: 0;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.14s ease;
}
.scanner-device-row + .scanner-device-row { border-top: 1px solid rgba(var(--v-theme-on-surface), 0.075); }
.scanner-device-row:hover,
.scanner-device-row:focus-visible { background: rgba(var(--v-theme-on-surface), 0.04); outline: none; }
.scanner-device-row.is-selected { background: rgba(var(--v-theme-primary), 0.085); }
.scanner-device-row.is-selected:hover { background: rgba(var(--v-theme-primary), 0.105); }
/* Verfügbare Geräte: Zeile selbst nicht klickbar, nur der Inline-„+"-Button. */
.scanner-device-row--static { cursor: default; }
.scanner-device-row--static:hover { background: transparent; }
.scanner-device-row__add { flex: 0 0 auto; }
.scanner-device-row__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 38px;
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.scanner-device-row__body { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 2px; }
.scanner-device-row__name { overflow: hidden; font-size: 0.9rem; font-weight: 620; text-overflow: ellipsis; white-space: nowrap; }
.scanner-device-row__meta { overflow: hidden; color: rgba(var(--v-theme-on-surface), 0.5); font-size: 0.74rem; text-overflow: ellipsis; white-space: nowrap; }
.scanner-device-row__selection {
  color: rgb(var(--v-theme-primary));
  opacity: 0;
  transition: opacity 0.14s ease;
}
.scanner-device-row__selection.is-visible { opacity: 1; }
.scanner-detail__danger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 3px;
}
.scanner-config { margin-top: 8px; padding-top: 16px; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.09); }
.scanner-config__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
  color: rgba(var(--v-theme-on-surface), 0.48);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.scanner-detail__form { display: grid; gap: 13px; padding: 12px 0 4px; }
.scanner-detail__toggle-row { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 58px; }
.scanner-detail__label { font-size: 0.86rem; font-weight: 600; }
.scanner-detail__hint { margin-top: 2px; color: rgba(var(--v-theme-on-surface), 0.52); font-size: 0.76rem; line-height: 1.4; }
.scanner-detail__technical { padding: 12px 0 2px; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.075); }
.scanner-detail__technical-label { color: rgba(var(--v-theme-on-surface), 0.48); font-size: 0.68rem; font-weight: 650; letter-spacing: 0.05em; text-transform: uppercase; }
.scanner-detail__technical-value { margin-top: 3px; color: rgba(var(--v-theme-on-surface), 0.75); font-size: 0.8rem; }
.scanner-detail__technical-meta { margin-top: 2px; color: rgba(var(--v-theme-on-surface), 0.45); font-size: 0.72rem; }
.scanner-detail__access { display: grid; gap: 12px; padding: 2px 0; }
.scanner-detail__access-warning { color: rgb(var(--v-theme-error)); font-size: 0.72rem; }
.scanner-remove-dialog__copy { margin: 0; color: rgba(var(--v-theme-on-surface), 0.72); line-height: 1.55; }
.scanner-recipient-chip :deep(.v-chip__prepend) { margin-inline: -5px 6px; }
@media (prefers-reduced-motion: reduce) {
  .scanner-device-row,
  .scanner-device-row__selection { transition: none; }
}
</style>

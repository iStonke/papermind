<template>
  <div class="pm-settings-content dev-settings-panel">
    <SettingsInfoCard
      icon="mdi-code-braces"
      title="Entwicklung"
      subtitle="Dev-Werkzeuge für diesen Browser. Änderungen gelten sofort."
    />

    <div class="dev-settings-context">
      <span class="dev-settings-context__badge">DEV</span>
      <div>
        <strong>Entwicklungsumgebung</strong>
        <div class="dev-settings-context__host">{{ origin }}</div>
      </div>
    </div>

    <div v-for="option in options" :key="option.key" class="pm-setting-row">
      <div class="pm-setting-content">
        <div :id="`dev-${option.key}-label`" class="pm-setting-label">{{ option.label }}</div>
        <div :id="`dev-${option.key}-description`" class="pm-setting-description">{{ option.description }}</div>
      </div>
      <v-switch
        :model-value="preferences[option.key]"
        :aria-labelledby="`dev-${option.key}-label`"
        :aria-describedby="`dev-${option.key}-description`"
        color="primary"
        density="comfortable"
        hide-details
        @update:model-value="setPreference(option.key, $event)"
      />
    </div>

    <div class="dev-settings-footer">
      <p v-if="storageAvailable">Wird nur in diesem Browser gespeichert.</p>
      <p v-else role="status">Browserspeicher nicht verfügbar. Änderungen gelten bis zum Neuladen.</p>
      <v-btn variant="text" size="small" prepend-icon="mdi-restore" @click="resetPreferences">
        Dev-Einstellungen zurücksetzen
      </v-btn>
    </div>
  </div>
</template>

<script setup>
import SettingsInfoCard from './SettingsInfoCard.vue';
import { useDevSettings } from '../composables/useDevSettings.js';

const { preferences, storageAvailable, setPreference, resetPreferences } = useDevSettings();
const origin = window.location.origin;
const options = [
  {
    key: 'showEnvironmentIndicator',
    label: 'DEV-System deutlich kennzeichnen',
    description: 'Zeigt eine gelbe DEV-Markierung mit Rahmen auf allen Seiten und ergänzt [DEV] im Browser-Tab.',
  },
  {
    key: 'showOnboardingLauncher',
    label: 'Onboarding-Schaltfläche anzeigen',
    description: 'Blendet „DEV · Onboarding“ unten rechts ein, um die Einführung jederzeit zu testen.',
  },
  {
    key: 'autoOpenOnboarding',
    label: 'Onboarding bei jedem Start öffnen',
    description: 'Öffnet die Einführung nach dem Neuladen oder Anmelden erneut – auch wenn sie bereits abgeschlossen wurde.',
  },
];
</script>

<style scoped>
.dev-settings-panel > .settings-info-card { margin-bottom: 0; }
.dev-settings-context {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 16px 0 6px;
  padding: 14px;
  border: 1px solid rgba(var(--v-theme-warning), 0.4);
  border-radius: 12px;
  background: rgba(var(--v-theme-warning), 0.08);
  font-size: 0.84rem;
}
.dev-settings-context > div { min-width: 0; }
.dev-settings-context__badge {
  padding: 4px 8px;
  border-radius: 5px;
  background: #fbbf24;
  color: #422006;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
}
.dev-settings-context__host {
  margin-top: 3px;
  color: rgba(var(--v-theme-on-surface), 0.65);
  overflow-wrap: anywhere;
}
.dev-settings-panel .v-switch { flex: 0 0 auto; }
.dev-settings-footer {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 8px;
  padding-top: 18px;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1);
}
.dev-settings-footer p {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.65);
  font-size: 0.8rem;
}
</style>

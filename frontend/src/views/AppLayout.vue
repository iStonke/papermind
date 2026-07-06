<template>
  <v-app
    class="papermind-app"
    :class="{ 'pm-no-animations': !settingsStore.animationsEnabled }"
    :data-color-variant="appColorVariant"
  >
    <router-view />

    <!-- Global verfügbar, damit das Zahnrad auf jeder Route funktioniert. Der
         Chunk (~114 kB) wird aber erst geladen/gemountet, sobald der Dialog das
         erste Mal geöffnet wird (settingsEverOpened rastet ein) → schnellerer
         Initial-Load. -->
    <SettingsDialog
      v-if="settingsEverOpened"
      :model-value="ui.settingsOpen"
      :initial-category="ui.settingsCategory"
      @update:model-value="ui.settingsOpen = $event"
      @reload-imports="ui.signalImportsReload()"
    />

    <!-- Konto-Dialog (Profil + Benutzerverwaltung), ebenfalls global und faul. -->
    <AccountDialog
      v-if="accountEverOpened"
      :model-value="ui.accountOpen"
      @update:model-value="ui.accountOpen = $event"
    />
  </v-app>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useTheme } from 'vuetify';

// Global gemountet, aber erst beim Öffnen gebraucht. SettingsDialog ist mit
// ~4000 Zeilen der größte Einzeldialog → als eigener Chunk ausgelagert, damit
// er den Initial-Load nicht belastet.
const AccountDialog = defineAsyncComponent(() => import('../components/AccountDialog.vue'));
const SettingsDialog = defineAsyncComponent(() => import('../components/SettingsDialog.vue'));
import { useSettingsStore } from '../stores/settings';
import { useUiStore } from '../stores/ui';
import { getBaseUrl } from '../api/client.js';
import { applyPaperMindVuetifyColors, resolvePaperMindColorVariant } from '../theme/tokens';

const theme = useTheme();
const settingsStore = useSettingsStore();
const ui = useUiStore();
const settingsDraft = settingsStore.settingsDraft;

const appColorVariant = computed(() => resolvePaperMindColorVariant(settingsDraft.ui.color_variant));

// Rasten beim ersten Öffnen ein und bleiben true, damit der Dialog danach seinen
// Zustand behält und der zugehörige Chunk nur bei Bedarf geladen wird.
const settingsEverOpened = ref(false);
const accountEverOpened = ref(false);
watch(() => ui.settingsOpen, (open) => { if (open) settingsEverOpened.value = true; }, { immediate: true });
watch(() => ui.accountOpen, (open) => { if (open) accountEverOpened.value = true; }, { immediate: true });

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme() {
  theme.global.name.value = resolveThemeName(settingsDraft.ui.theme_mode);
  applyPaperMindVuetifyColors(theme, settingsDraft.ui.color_variant || 'teal');
}

// Theme live nachführen (greift auch, wenn man nur auf den Konto-Seiten ist).
watch(() => settingsDraft.ui.color_variant, (variant) => applyPaperMindVuetifyColors(theme, variant || 'teal'));
watch(() => settingsDraft.ui.theme_mode, () => applyTheme());

let mediaQuery = null;
function handleSystemThemeChange() {
  if (settingsDraft.ui.theme_mode === 'system') applyTheme();
}

onMounted(async () => {
  // Einstellungen früh laden, damit das Theme app-weit korrekt steht.
  try {
    await settingsStore.fetchSettings(getBaseUrl(), { silent: true });
  } catch {
    /* Theme fällt sonst auf Defaults zurück – unkritisch. */
  }
  applyTheme();
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', handleSystemThemeChange);
});

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', handleSystemThemeChange);
});
</script>

<template>
  <v-app
    class="papermind-app"
    :class="{ 'pm-no-animations': !settingsStore.animationsEnabled }"
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
      @show-onboarding="showOnboardingFromSettings"
    />

    <!-- Konto-Dialog (Profil + Benutzerverwaltung), ebenfalls global und faul. -->
    <AccountDialog
      v-if="accountEverOpened"
      :model-value="ui.accountOpen"
      @update:model-value="ui.accountOpen = $event"
    />

    <!-- Ziel für eigene Overlays INNERHALB von .papermind-app, damit die
         --pm-*-Kontur-Tokens greifen (anders als bei nach außen teleportierten
         v-dialogs). Die Command-Palette teleportiert hierher. -->
    <div id="pm-overlays"></div>

    <!-- Command-Palette (⌘K). Wie die anderen Overlays global + faul: erst beim
         ersten Öffnen gemountet. -->
    <CommandPalette
      v-if="paletteEverOpened"
      :model-value="ui.paletteOpen"
      @update:model-value="ui.paletteOpen = $event"
    />

    <OnboardingDialog
      v-if="onboardingEverOpened"
      :model-value="ui.onboardingOpen"
      :user-name="onboardingUserName"
      @update:model-value="ui.onboardingOpen = $event"
      @dismiss="completeOnboarding(false)"
      @finish="completeOnboarding(true)"
    />

    <v-btn
      v-if="isDev"
      class="onboarding-dev-launcher"
      size="small"
      variant="elevated"
      prepend-icon="mdi-creation"
      @click="ui.openOnboarding('dev')"
    >
      DEV · Onboarding
    </v-btn>
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
const CommandPalette = defineAsyncComponent(() => import('../components/CommandPalette.vue'));
const OnboardingDialog = defineAsyncComponent(() => import('../components/OnboardingDialog.vue'));
import { useSettingsStore } from '../stores/settings';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useGlobalKeyboard } from '../composables/useGlobalKeyboard';
import { getBaseUrl } from '../api/client.js';

const theme = useTheme();
const settingsStore = useSettingsStore();
const ui = useUiStore();
const authStore = useAuthStore();
const settingsDraft = settingsStore.settingsDraft;
const isDev = import.meta.env.DEV;
const onboardingUserName = computed(() => (
  authStore.user?.display_name?.trim()
  || authStore.user?.username?.trim()
  || ''
));

// Rasten beim ersten Öffnen ein und bleiben true, damit der Dialog danach seinen
// Zustand behält und der zugehörige Chunk nur bei Bedarf geladen wird.
const settingsEverOpened = ref(false);
const accountEverOpened = ref(false);
const paletteEverOpened = ref(false);
const onboardingEverOpened = ref(false);
watch(() => ui.settingsOpen, (open) => { if (open) settingsEverOpened.value = true; }, { immediate: true });
watch(() => ui.accountOpen, (open) => { if (open) accountEverOpened.value = true; }, { immediate: true });
watch(() => ui.paletteOpen, (open) => { if (open) paletteEverOpened.value = true; }, { immediate: true });
watch(() => ui.onboardingOpen, (open) => { if (open) onboardingEverOpened.value = true; }, { immediate: true });

const ONBOARDING_PENDING_KEY = 'pm.onboarding.after-register';
let onboardingOpenTimer = null;
let onboardingActionTimer = null;

function onboardingCompletionKey() {
  return authStore.user?.id ? `pm.onboarding.completed.${authStore.user.id}` : '';
}

function completeOnboarding(openImport) {
  const key = onboardingCompletionKey();
  if (key) window.localStorage.setItem(key, '1');
  window.sessionStorage.removeItem(ONBOARDING_PENDING_KEY);
  ui.closeOnboarding();

  if (openImport) {
    // Erst das Fenster ausblenden; danach öffnet der bestehende Workspace-Flow
    // den Import-Dialog, ohne zwei Modals übereinander zu legen.
    onboardingActionTimer = window.setTimeout(() => ui.requestAction('import'), 260);
  }
}

function showOnboardingFromSettings() {
  ui.closeSettings();
  if (onboardingOpenTimer) window.clearTimeout(onboardingOpenTimer);
  // Den Einstellungsdialog erst ausblenden, damit die beiden Fenster nicht
  // für einen Frame übereinander liegen und der Fokus sauber weitergereicht wird.
  onboardingOpenTimer = window.setTimeout(() => {
    ui.openOnboarding('settings');
  }, 260);
}

function scheduleInitialOnboarding() {
  const pendingRegistration = window.sessionStorage.getItem(ONBOARDING_PENDING_KEY);
  const requestedInDev = isDev && new URLSearchParams(window.location.search).get('onboarding') === '1';
  if (!pendingRegistration && !requestedInDev) return;

  onboardingOpenTimer = window.setTimeout(() => {
    ui.openOnboarding(pendingRegistration ? 'registration' : 'dev-query');
  }, 420);
}

// Globales ⌘K / Ctrl+K schaltet die Command-Palette um. Bewusst überall aktiv,
// auch wenn der Fokus in einem Eingabefeld liegt (z. B. Sidebar-Suche).
function handleGlobalShortcut(event) {
  if ((event.metaKey || event.ctrlKey) && !event.altKey && (event.key === 'k' || event.key === 'K')) {
    event.preventDefault();
    ui.togglePalette();
  }
}
useGlobalKeyboard(handleGlobalShortcut);

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme() {
  const themeName = resolveThemeName(settingsDraft.ui.theme_mode);
  theme.global.name.value = themeName;
  document.documentElement.dataset.theme = themeName;
}

// Theme live nachführen (greift auch, wenn man nur auf den Konto-Seiten ist).
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
  scheduleInitialOnboarding();
});

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', handleSystemThemeChange);
  if (onboardingOpenTimer) window.clearTimeout(onboardingOpenTimer);
  if (onboardingActionTimer) window.clearTimeout(onboardingActionTimer);
});
</script>

<style scoped>
.onboarding-dev-launcher {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 20;
  border: 1px solid rgba(var(--v-theme-primary), 0.34);
  background: rgb(var(--v-theme-surface-2)) !important;
  color: rgb(var(--v-theme-primary));
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18) !important;
  letter-spacing: 0.02em;
}

@media (max-width: 720px) {
  .onboarding-dev-launcher {
    right: 12px;
    bottom: 12px;
  }
}
</style>

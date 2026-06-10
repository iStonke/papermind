<template>
  <v-app
    class="papermind-app"
    :class="{ 'pm-no-animations': !settingsStore.animationsEnabled }"
    :data-color-variant="appColorVariant"
    :data-glass="glassActive ? 'on' : null"
  >
    <div v-if="glassActive" class="glass-bg-layer" aria-hidden="true">
      <KnowledgeGraphBackground
        :palette="glassPalette"
        :density="glassDensity"
        :interactive="glassInteractive"
      />
    </div>

    <router-view />

    <!-- Global gemountet, damit das Zahnrad auf jeder Route funktioniert. -->
    <SettingsDialog
      :model-value="ui.settingsOpen"
      :initial-category="ui.settingsCategory"
      @update:model-value="ui.settingsOpen = $event"
      @reload-imports="ui.signalImportsReload()"
    />

    <!-- Konto-Dialog (Profil + Benutzerverwaltung), ebenfalls global. -->
    <AccountDialog
      :model-value="ui.accountOpen"
      @update:model-value="ui.accountOpen = $event"
    />
  </v-app>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useTheme } from 'vuetify';

import AccountDialog from '../components/AccountDialog.vue';
import KnowledgeGraphBackground from '../components/KnowledgeGraphBackground.vue';
import SettingsDialog from '../components/SettingsDialog.vue';
import { useSettingsStore } from '../stores/settings';
import { useUiStore } from '../stores/ui';
import { getBaseUrl } from '../api/client.js';
import { applyPaperMindVuetifyColors, getGlassPalette, resolvePaperMindColorVariant } from '../theme/tokens';

const theme = useTheme();
const settingsStore = useSettingsStore();
const ui = useUiStore();
const settingsDraft = settingsStore.settingsDraft;

const appColorVariant = computed(() => resolvePaperMindColorVariant(settingsDraft.ui.color_variant));

// ── Glass-Look (Aurora-Hintergrund) ──────────────────────────────────────────
const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Grobzeiger/schmaler Viewport -> mobil, reduzierte Last.
const coarsePointer = ref(
  typeof window !== 'undefined' && window.matchMedia
    ? window.matchMedia('(pointer: coarse)').matches
    : false
);
const narrowViewport = ref(typeof window !== 'undefined' ? window.innerWidth < 700 : false);
function updateViewport() {
  narrowViewport.value = window.innerWidth < 700;
}
const isMobileLike = computed(() => coarsePointer.value || narrowViewport.value);

const glassActive = computed(
  () => Boolean(settingsDraft.ui.glass_enabled) && settingsStore.animationsEnabled && !prefersReducedMotion
);
const isDarkTheme = computed(() => Boolean(theme.global.current.value?.dark));
const glassPalette = computed(() => getGlassPalette(appColorVariant.value, isDarkTheme.value));
// Im App-Kontext etwas ruhiger als der Login; mobil deutlich reduziert.
const glassDensity = computed(() => (isMobileLike.value ? 0.45 : 0.8));
// Maus-Interaktion (Linien zum Cursor) nur im Login, nicht app-weit.
const glassInteractive = false;

function resolveThemeName(mode) {
  if (mode === 'light' || mode === 'dark') return mode;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function applyTheme() {
  theme.global.name.value = resolveThemeName(settingsDraft.ui.theme_mode);
  applyPaperMindVuetifyColors(theme, settingsDraft.ui.color_variant || 'slate');
}

// Theme live nachführen (greift auch, wenn man nur auf den Konto-Seiten ist).
watch(() => settingsDraft.ui.color_variant, (variant) => applyPaperMindVuetifyColors(theme, variant || 'slate'));
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
  window.addEventListener('resize', updateViewport, { passive: true });
});

onBeforeUnmount(() => {
  if (mediaQuery) mediaQuery.removeEventListener('change', handleSystemThemeChange);
  window.removeEventListener('resize', updateViewport);
});
</script>

<style scoped>
/* Aurora-Hintergrund hinter dem App-Inhalt. z-index:-1 haelt ihn im
   Stacking-Context des v-application__wrap unter den (deckenden) Panels,
   aber ueber der Aurora-Grundschicht der App. */
.glass-bg-layer {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
}
</style>

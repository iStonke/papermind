<template>
  <section class="dashboard" aria-label="Übersicht">
    <div class="dashboard__scroll">
      <!-- 1) Kopfzeile -->
      <header class="dash-head">
        <div class="dash-head__intro">
          <h1 class="dash-head__greeting">{{ greeting }}</h1>
          <p class="dash-head__meta">{{ headMeta }}</p>
        </div>
        <div class="dash-head__actions">
          <button type="button" class="dash-btn dash-btn--primary" @click="emit('open-import')">
            <v-icon size="15">mdi-tray-arrow-up</v-icon>
            Importieren
          </button>
          <button type="button" class="dash-btn" @click="emit('open-ai')">
            <v-icon size="15">mdi-creation</v-icon>
            KI fragen
          </button>
        </div>
      </header>

      <!-- Leerer Zustand -->
      <div v-if="isEmpty" class="dash-empty">
        <div class="dash-empty__icon"><v-icon size="34">mdi-view-dashboard-outline</v-icon></div>
        <h2 class="dash-empty__title">Noch keine Dokumente</h2>
        <p class="dash-empty__text">Sobald du dein erstes Dokument ablegst, erscheinen hier Kennzahlen und Auswertungen.</p>
        <button type="button" class="dash-btn dash-btn--primary dash-empty__cta" @click="emit('open-import')">
          <v-icon size="16">mdi-tray-arrow-up</v-icon>
          Erstes Dokument importieren
        </button>
      </div>

      <!--
        Phase 1: Die Übersicht besteht aus eigenständigen Widget-Komponenten
        (siehe components/dashboard/). Sie werden hier vorerst im bestehenden
        festen Raster platziert – gleiche Wrapper, gleiche Klassen, gleiche
        Reihenfolge wie zuvor, damit sich optisch nichts ändert. Phase 2 ersetzt
        dieses Raster durch ein konfigurierbares Board aus derselben Registry.
      -->
      <template v-else>
        <!-- 2) Kennzahlen-Band -->
        <component :is="widgets.stats.component" />

        <!-- 3) Visualisierungen -->
        <div class="dash-viz">
          <component :is="widgets.documentsPerYear.component" />
          <div class="dash-viz__side">
            <component :is="widgets.topCorrespondents.component" />
          </div>
        </div>

        <!-- 4) Untere Inhalte -->
        <div class="dash-lower">
          <div class="dash-lower__main">
            <component :is="widgets.recentImports.component" />
            <component :is="widgets.openTasks.component" />
            <component :is="widgets.topSearches.component" />
          </div>
          <div class="dash-lower__side">
            <component :is="widgets.distribution.component" />
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, provide } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth.js';
import { useDashboardStore } from '../stores/dashboard.js';
import { DASHBOARD_ACTIONS } from '../components/dashboard/dashboardShared.js';
import { DASHBOARD_WIDGETS } from '../components/dashboard/widgetRegistry.js';
import '../components/dashboard/dashboard.css';

const emit = defineEmits([
  'open-import',
  'open-ai',
  'open-document',
  'attention-select',
  'show-all-recent',
  'search-term',
  'year-select',
]);

const dashboardStore = useDashboardStore();
const auth = useAuthStore();
const { overview, hasLoadedOnce } = storeToRefs(dashboardStore);

const widgets = DASHBOARD_WIDGETS;

// Host-Aktionen: die Widgets lesen ihre Daten selbst aus dem Store und melden
// Interaktionen über diesen provide/inject-Kanal zurück, der sie auf die
// bestehenden Component-Events des Elternteils (DocumentsWorkspace) abbildet.
provide(DASHBOARD_ACTIONS, {
  openImport: () => emit('open-import'),
  openAi: () => emit('open-ai'),
  openDocument: (id) => emit('open-document', id),
  attentionSelect: (key) => emit('attention-select', key),
  showAllRecent: () => emit('show-all-recent'),
  searchTerm: (term) => emit('search-term', term),
  yearSelect: (payload) => emit('year-select', payload),
});

onMounted(() => {
  void dashboardStore.fetchOverview();
});

const isEmpty = computed(() => hasLoadedOnce.value && overview.value.stats.documents_total === 0);

// ── Kopfzeile ───────────────────────────────────────────────────────────────
const userGreetingName = computed(() => {
  const name = auth.user?.display_name || auth.username;
  return String(name || '').trim();
});

const greeting = computed(() => {
  const h = new Date().getHours();
  const part = h < 5 ? 'Gute Nacht' : h < 11 ? 'Guten Morgen' : h < 18 ? 'Guten Tag' : 'Guten Abend';
  return userGreetingName.value ? `${part}, ${userGreetingName.value}` : part;
});

const headMeta = computed(() =>
  new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
);
</script>

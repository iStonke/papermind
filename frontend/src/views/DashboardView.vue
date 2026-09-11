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
          <button
            v-if="!isEmpty"
            type="button"
            class="dash-btn"
            :class="{ 'dash-btn--primary': editing }"
            @click="onWidgetAction"
          >
            <v-icon size="15">{{ editing ? 'mdi-check' : 'mdi-view-dashboard-edit-outline' }}</v-icon>
            {{ editing ? 'Fertig' : 'Anpassen' }}
          </button>
        </div>
      </header>

      <!-- Leerer Zustand -->
      <div v-if="isEmpty" class="dash-empty">
        <div class="dash-empty__icon"><v-icon size="34">mdi-view-dashboard-outline</v-icon></div>
        <h2 class="dash-empty__title">Noch keine Dokumente</h2>
        <p class="dash-empty__text">Sobald du dein erstes Dokument ablegst, erscheinen hier Kennzahlen und Auswertungen.</p>
      </div>

      <!--
        Phase 2: Konfigurierbares Board. Die Widgets (components/dashboard/,
        gespeist aus der Registry) liegen in einem gridstack-Raster, das sich im
        Bearbeitungsmodus verschieben/skalieren lässt; Layout wird gemerkt.
      -->
      <DashboardBoard ref="dashboardBoard" v-else v-model:editing="editing" />
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth.js';
import { useDashboardStore } from '../stores/dashboard.js';
import { DASHBOARD_ACTIONS } from '../components/dashboard/dashboardShared.js';
import DashboardBoard from '../components/dashboard/DashboardBoard.vue';
import '../components/dashboard/dashboard.css';

const emit = defineEmits([
  'open-document',
  'attention-select',
  'show-all-recent',
  'search-term',
  'year-select',
]);

const dashboardStore = useDashboardStore();
const auth = useAuthStore();
const { overview, hasLoadedOnce } = storeToRefs(dashboardStore);

// Bearbeitungsmodus des Boards (Umschalter sitzt in der Kopfzeile).
const editing = ref(false);
const dashboardBoard = ref(null);

function openWidgetManager() {
  dashboardBoard.value?.openManager();
}

function onWidgetAction() {
  if (editing.value) {
    editing.value = false;
    return;
  }
  openWidgetManager();
}

// Host-Aktionen: die Widgets lesen ihre Daten selbst aus dem Store und melden
// Interaktionen über diesen provide/inject-Kanal zurück, der sie auf die
// bestehenden Component-Events des Elternteils (DocumentsWorkspace) abbildet.
provide(DASHBOARD_ACTIONS, {
  openDocument: (id) => emit('open-document', id),
  attentionSelect: (key) => emit('attention-select', key),
  showAllRecent: () => emit('show-all-recent'),
  searchTerm: (term) => emit('search-term', term),
  yearSelect: (payload) => emit('year-select', payload),
});

function refreshAfterNoteSave() {
  void dashboardStore.fetchOverview();
}

onMounted(() => {
  window.addEventListener('papermind:note-content-saved', refreshAfterNoteSave);
  void dashboardStore.fetchOverview();
});

onBeforeUnmount(() => {
  window.removeEventListener('papermind:note-content-saved', refreshAfterNoteSave);
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
